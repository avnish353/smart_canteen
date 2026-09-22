from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from django.db.models import Q
from adminpanel.models import MenuItem,OrderItem,Order,PaymentLog
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def homepage(request):
    items = MenuItem.objects.filter(available=True)
    return render(request, 'homepage.html', {'items': items,})

def menu(request):
    items = MenuItem.objects.filter(available=True)
    cart = request.session.get('cart', {})  
    cart_count = sum(cart.values())  
    return render(request, 'menu.html', {'items': items,"cart_count": cart_count})

def cart(request):
    cart = request.session.get('cart', {})  # {item_id: quantity}

    # Handle + / - buttons
    if request.method == "POST":
        item_id = str(request.POST.get("item_id"))
        action = request.POST.get("action")

        if item_id in cart:
            if action == "plus":
                cart[item_id] += 1
            elif action == "minus":
                cart[item_id] -= 1
                if cart[item_id] <= 0:
                    del cart[item_id]

        request.session['cart'] = cart
        return redirect("cart")

    # Prepare items for display
    items = []
    total = 0
    invalid_ids = []

    for item_id, quantity in cart.items():
        # SAFER lookup
        item = MenuItem.objects.filter(id=item_id).first()

        if not item:
            invalid_ids.append(item_id)
            continue

        item.quantity = quantity
        item.subtotal = item.price * quantity
        items.append(item)
        total += item.subtotal

    # Remove deleted or invalid items from session
    if invalid_ids:
        for x in invalid_ids:
            cart.pop(x, None)
        request.session['cart'] = cart

    return render(request, 'cart.html', {
        'items': items,
        'total': total
    })

    
def add_to_cart(request, item_id):
    cart = request.session.get('cart', {})

    item_id = str(item_id)

    if item_id in cart:
        cart[item_id] += 1
    else:
        cart[item_id] = 1

    request.session['cart'] = cart

    return redirect("menu") 

@login_required
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('menu')

    items = []
    total = 0
    for item_id, quantity in cart.items():
        item = get_object_or_404(MenuItem, id=item_id)
        item.quantity = quantity
        item.subtotal = item.price * quantity
        items.append(item)
        total += item.subtotal

    return render(request, 'checkout.html', {
        'items': items,
        'total': total
    })
 
@login_required
def my_account(request):
    user = request.user
    phone = getattr(request.user.profile, 'mobile', 'N/A')

    # Get all past orders for this user, newest first
    orders = Order.objects.filter(customer=user, status="Picked Up").order_by('-timestamp')

    context = {
        'user': user,
        'mobile': phone,
        'orders': orders,
    }
    return render(request, 'my_account.html', context)   
    
@login_required
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        # You can save this to DB, send email, etc.
        print("New Contact Message:", name, email, phone, message)

        messages.success(request, "Your message has been sent successfully!")

        return redirect("contact")

    return render(request, "contact.html")

@login_required
def customer_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-timestamp')
    return render(request, 'customer_orders.html', {'orders': orders})

@login_required
def reorder(request, order_id):
    if request.method == "POST":
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        cart = request.session.get('cart', {})

        for item in order.orderitem_set.all():
            item_id = str(item.item.id)
            if item_id in cart:
                cart[item_id] += item.quantity
            else:
                cart[item_id] = item.quantity

        request.session['cart'] = cart
        return redirect('cart')  # redirect to cart page
    return redirect('customer_orders')  # fallback

def search_food(request):
    query = request.GET.get("q", "").strip()  # get search query
    
    # Filter by name OR category OR description
    results = MenuItem.objects.filter(
        Q(name__icontains=query) |
        Q(category__icontains=query)
    ) if query else MenuItem.objects.all()
    
    # Example cart count (adjust to your cart logic)
    cart_count = request.session.get('cart_count', 0)
    
    return render(request, "search_results.html", {
        "query": query,
        "results": results,
        "cart_count": cart_count
    })




@login_required
def payment_page(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.info(request, "Your cart is empty!")
        return redirect('menu')

    # Calculate total amount
    total = 0
    for item_id, quantity in cart.items():
        item = MenuItem.objects.get(id=item_id)
        total += item.price * quantity

    if request.method == "POST":
        fullname = request.POST.get("fullname")
        email = request.POST.get("email")
        card_number = request.POST.get("card_number")
        phone = getattr(request.user.profile, 'mobile', 'N/A')
        cvv = request.POST.get("cvv")
        expiry = request.POST.get("expiry")
        order_datetime = datetime.now()

        # Simple dummy card validation
        if len(card_number) == 16 and len(cvv) == 3:

            # Create order
            order = Order.objects.create(
                customer=request.user,
                total_price=total,
                status="Paid"
            )

            # LOOP THROUGH CART ITEMS
            for item_id, quantity in cart.items():
                item = MenuItem.objects.get(id=item_id)

                # Save order item
                OrderItem.objects.create(
                    order=order,
                    item=item,
                    quantity=quantity
                )



            # CLEAR CART
            request.session['cart'] = {}

            # SEND DATA TO SUCCESS PAGE
            bill_data = {
                "fullname": fullname,
                "email": email,
                "phone": phone,
                "amount": total,
                "order_datetime": order_datetime
            }

            return render(request, "payment_success.html", bill_data)

        else:
            messages.error(request, "Invalid card details!")
            return redirect("payment_page")

    return render(request, "payment_page.html", {"total": total})



@login_required
def payment_success(request):
    cart = request.session.get('cart')

    if not cart:
        return redirect("homepage")  # or cart page

    total = 0
    order = Order.objects.create(customer=request.user, total_price=0)

    for item_id, quantity in cart.items():
        item = get_object_or_404(MenuItem, id=item_id)
        OrderItem.objects.create(order=order, item=item, quantity=quantity)
        total += item.price * quantity

    order.total_price = total
    order.save()

    PaymentLog.objects.create(
        order=order,
        amount=total,
        method="Card"
    )

    request.session['cart'] = {}  # clear cart

    phone = getattr(request.user.profile, 'mobile', 'N/A')

    return render(request, "payment_success.html", {
        "fullname": request.user.get_full_name(),
        "email": request.user.email,
        "phone": phone,
        "amount": total,
        "order_datetime": datetime.now(),
        "order_id": order.id,   # ✅ SAFE
    })
    

@login_required
def download_receipt(request):
    data = {
        "fullname": request.GET.get("name"),
        "email": request.GET.get("email"),
        "phone": request.GET.get("phone"),
        "amount": request.GET.get("amount"),
        "date": request.GET.get("date"),
        "time": request.GET.get("time"),
    }

    template = get_template("receipt_template.html")
    html = template.render(data)

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="receipt.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating PDF")

    return response
