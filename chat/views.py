from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.dispatch import receiver
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, user_logged_in, user_logged_out
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from keras.src.utils import pad_sequences

from .models import PrivateMessage, UserStatus
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib import messages
import json
import random
import pickle
import numpy as np
import tensorflow as tf
from nltk.tokenize import word_tokenize

model = tf.keras.models.load_model("chatbot_model.h5")
with open("tokenizer.pkl", "rb") as file:
    tokenizer = pickle.load(file)
with open("encoder.pkl", "rb") as file:
    encoder = pickle.load(file)
with open('intents.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

GREETING_MESSAGE = "Hello!... I'm your Ari. How can I assist you today?"

# def predict_class(text):
#     if not text.strip():
#         return None
#     tokens = word_tokenize(text.lower())
#     filtered_tokens = [word for word in tokens if word in tokenizer.word_index]
#     if not filtered_tokens:
#         return None
#     seq = tokenizer.texts_to_sequences([filtered_tokens])
#     seq = pad_sequences(seq, maxlen=model.input_shape[1], padding="post")
#     prediction = model.predict(seq)[0]
#     predicted_index = np.argmax(prediction)
#
#     return encoder.classes_[predicted_index]

def predict_class(text, confidence_threshold=0.7):
    if not text.strip():
        return None
    tokens = word_tokenize(text.lower())
    filtered_tokens = [word for word in tokens if word in tokenizer.word_index]
    if not filtered_tokens:
        return None
    seq = tokenizer.texts_to_sequences([filtered_tokens])
    seq = pad_sequences(seq, maxlen=model.input_shape[1], padding="post")
    prediction = model.predict(seq)[0]
    predicted_index = np.argmax(prediction)
    confidence = prediction[predicted_index]
    if confidence < confidence_threshold:
        return None
    return encoder.classes_[predicted_index]

def chatbot_response(request):
    if request.method == "GET":
        user_message = request.GET.get("message", "").strip()
        if not user_message:
            return JsonResponse({"response": GREETING_MESSAGE})
        tag = predict_class(user_message)
        if tag:
            response_list = next((intent["response"] for intent in data["intents"] if intent["tag"] == tag), [])
            response = random.choice(response_list) if response_list else "I'm not sure I understand. Can you rephrase?"
        else:
            response = "Sorry, I couldn't understand that. Please ask again."
        return JsonResponse({"response": response})
    return JsonResponse({"response": "Invalid request method. Use GET."})

def chatbot(request):
    return render(request, 'chatbot.html')

@receiver(user_logged_in)
def set_online(sender, request, user, **kwargs):
    user.is_online = True
    user.save()

@receiver(user_logged_out)
def set_offline(sender, request, user, **kwargs):
    user.is_online = False
    user.save()

def send_message(sender, recipient, message_text):
    message = PrivateMessage.objects.create(sender=sender, recipient=recipient, text=message_text, is_read=False)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{recipient.username}",
        {
            "type": "notify_new_message",
        }
    )

    return message


class LoginRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        return redirect('users')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('users')
        else:
            return render(request, 'chat/login.html', {'error': 'Invalid Credentials'})
    return render(request, 'chat/login.html')

def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! You can log in now.")
            return redirect('login')
        else:
            messages.error(request, "Error in registration. Please check the form.")
    else:
        form = UserCreationForm()

    return render(request, 'chat/signup.html', {'form': form})

@csrf_exempt
def save_message(request):
    if request.method == 'POST':
        message_content = request.POST.get('message')
        username = request.POST.get('username')
        try:
            user = User.objects.get(username=username)
            message = PrivateMessage.objects.create(
                recipient=user, sender=request.user, text=message_content
            )
            return JsonResponse({'status': 'success', 'message_id': message.id}, status=200)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def user_list_view(request):
    users = User.objects.exclude(id=request.user.id)
    return render(request, 'chat/users.html', {'users': users})

@login_required
def chat_view(request, username):
    user = request.user
    recipient = get_object_or_404(User, username=username)
    PrivateMessage.objects.filter(sender=request.user, recipient=recipient, is_read=False).update(is_read=True)
    messages = PrivateMessage.objects.filter(
        Q(sender=user, recipient=recipient) | Q(sender=recipient, recipient=user)
    ).order_by('timestamp')
    print("Messages Retrieved:", messages)
    return render(request, 'chat/users.html', {
        'messages': messages,
        'recipient': recipient,
        'user': user,
    })

def screenshare_view(request):
    return render(request, 'chat/users.html')

def users_view(request):
    return render(request, 'chat/users.html')

def custom_500_error(request):
    return render(request, '500.html', status=500)

@login_required
def fetch_new_messages(request, username):
    user = request.user
    messages = PrivateMessage.objects.filter(
        Q(sender__username=username, recipient=user) |
        Q(sender=user, recipient__username=username)
    ).order_by('-timestamp')

    message_data = [{
        'sender': message.sender.username,
        'content': message.text,
        'timestamp': message.timestamp.strftime('%H:%M')
    } for message in messages]

    return JsonResponse({'messages': message_data})

@csrf_exempt
@login_required
def mark_as_read(request):
    if request.method == "POST":
        username = request.POST.get("username")
        user = request.user
        PrivateMessage.objects.filter(sender__username=username, recipient=user, is_read=False).update(is_read=True)
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
def screen_share(request):
    return render(request, 'users.html')

@login_required
def fetch_unread_count(request, username):
    user = request.user
    recipient = User.objects.filter(username=username).first()
    if not recipient:
        return JsonResponse({'error': 'User not found'}, status=404)
    unread_count = PrivateMessage.objects.filter(
        recipient=recipient,
        is_read=False
    ).count()
    return JsonResponse({'unread_count': unread_count})

@login_required
def get_old_messages(request, sender, recipient, username):
    user = request.user
    recipient = User.objects.filter(username=username).first()
    messages = PrivateMessage.objects.filter(
        (Q(sender__username=sender, recipient__username=recipient) |
         Q(sender__username=recipient, recipient__username=sender))
    ).order_by("timestamp")
    message_data = [
        {
            "id": msg.id,
            "sender": msg.sender.username,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%H:%M")
        }
        for msg in messages
    ]
    return JsonResponse({"messages": message_data})

def load_messages(request, sender, recipient):
    messages = PrivateMessage.objects.filter(
        sender__username__in=[sender, recipient],
        recipient__username__in=[sender, recipient]
    ).order_by("timestamp")

    return JsonResponse({"messages": [
        {"sender": msg.sender.username, "content": msg.content, "timestamp": msg.timestamp.strftime("%H:%M")}
        for msg in messages
    ]})


def custom_logout_view(request):
    logout(request)
    return redirect('/')

def custom_404_view(request, exception):
    return render(request, 'chat/404.html', status=404)

def custom_csrf_failure_view(request, reason=""):
    return render(request, "403_csrf.html", status=403)

def custom_500_view(request, exception):
    return render(request, '500.html', status=500)