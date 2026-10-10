from django import forms
class CartAddProductForm(forms.Form):
 quantity = forms.IntegerField(min_value=1, max_value=20, initial=1)
# False on the detail page ("add 2 more"), True on the cart page ("set it to 2")
override = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput)
 