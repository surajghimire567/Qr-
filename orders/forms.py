from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["full_name", "phone", "address"]   # NEVER user, total_amount, status

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip().replace(" ", "")
        if not (phone.isdigit() and len(phone) == 10):
            raise forms.ValidationError("Enter a 10-digit mobile number.")
        return phone