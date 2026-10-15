from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    checkout_key = forms.UUIDField(widget=forms.HiddenInput)

    class Meta:
        model = Order
        fields = ["full_name", "phone", "address", "checkout_key"]

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip().replace(" ", "")
        if not (phone.isdigit() and len(phone) == 10):
            raise forms.ValidationError("Enter a 10-digit mobile number.")
        return phone
