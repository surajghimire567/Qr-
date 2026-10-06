# Qr-
Personal 
day 1 :
installment 

QUESTION :
1)Why does OrderItem store its own price when Product already has one?
=product price is without shipping cost and appiled coupon or discount,so for that changes :orderitem have its own price too.
2)If an admin deletes a Category that still has Products, what should happen? What about deleting a
Product that has been ordered?
=product shouldbe removed too along with deletion of category.
-should ask for warning ,"as item is order even deleteing item cannot stop, you should process the respective order or notify customer about deletion as due to reasons.
3)Why is money a DecimalField and never a FloatField?
=money traqnscation is always done integerr value no flaoating value which is standard for effective buying selling.
4) Which field will tell you whether an order is safe to ship? Who is allowed to change it?
=order table ,its status aqnd shipping info will tell orrder self to ship.if technical or stock problem admin is allowed or if customer want to cancel ,he can apply for change but donot allowed to change though.
5)Why is there no Cart model?
=to have cart ,user must create account and a active session .