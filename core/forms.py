from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class CustomerRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, label="Full Name",
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Rahul Nair'}))
    phone_number = forms.CharField(max_length=15, required=True, label="Phone Number",
                                  widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9876543210'}))
    email = forms.EmailField(required=True, label="Email Address",
                             widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
                               label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
                                       label="Confirm Password")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose username'}),
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data


class ContactMessageForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}))
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Phone Number'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your Email (Optional)'}))
    subject = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject / Tournament / Booking inquiry'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tell us how we can help you...'}))
