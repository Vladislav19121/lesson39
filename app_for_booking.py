from aiohttp import web
from datetime import datetime
import asyncio
import aiosmtplib
import bcrypt #для хеширования пароля 
import jwt
import os
import json
import logging
import re #для проверки валидности email 

# JWT_SECRET = os.environ.get("JWT_SECRET", "your-secret-key")
# JWT_ALGORITHM = "HS256" 

# '''в целом вроде понятно, что здесь происходит, 
# но на рандом jwt не создавал, будет дефолтным, знаю что не безопасно 
# '''

EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'gvlad2322@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
PASSWORD_MIN_LENGTH = 4
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

services = []
booked_services = []
next_id = 1
users = {}

# def create_jwt(user_email):
#     payload = {"email": user_email,
#                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
#                }
#     token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
#     return token

# def decode_jwt(token):
#     try:
#         payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#         return payload
#     except jwt.ExpiredSignatureError:
#         print("Токен истек")
#         return None
#     except jwt.InvalidTokenError:
#         print("Неверный токен")
#         return None
    
async def register(request):
    try:
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
    
        if not email or not password:
            return web.json_response({"error": "Необоходимо указать 'email' и 'password"},
                                     status=400)
        if not re.match(EMAIL_REGEX, email):
            return web.json_response({"error": "Неверный формат email"}, status=400)
        
        if len(password) < PASSWORD_MIN_LENGTH:
            return web.json_response({"error": f"Пароль должен быть не менее {PASSWORD_MIN_LENGTH} символов"}, status = 400)
        
        if email in users:
            return web.json_response({"error": f"Пользователь с email - {email} уже существует"}, status = 409)
        
        # hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    
        # users[email] = {"password_hash": hashed_password}

        # jwt_token = create_jwt(email)
        users[email] = password

        return web.json_response({"success": f'Вы успешно зарегистрировались, {email}!'}, status=201)
    
    except:
        return web.json_response({"error": "Неверный формат JSON"}, status=400)
        
async def login(request):
    try:
        logging.info("Начало функции login")
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        logging.info(f"Получены email: {email}, password: {password}")

        if not email or not password:
            return web.json_response({"error": "Необходимо указать email и пароль"}, status=400)
        
        user = users.get(email)
        if not user:
            return web.json_response({"error": "Неверный email или пароль"}, status=401)
        # if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
        #      return web.json_response({"error": "Неверный email или пароль"}, status=401)
        
        # jwt_token = create_jwt(email)
        return web.json_response({"success": f'Вы успешно залогинились, {email}!'}, status=200)
    
    except json.JSONDecodeError:
        return web.json_response({"error": "Неверный формат JSON"}, status=400)
    

async def get_users(request):

    user_list = []
    for email, password in users.items():
        user_list.append({"email": email, "password": password})
    return web.json_response(user_list, status=200)

async def get_booked_services(request):
    get_booked_services = []
    for i in booked_services:
        get_booked_services.append(i)
    return web.json_response(get_booked_services, status=200)
    

async def create_service(request):

    global services, next_id
    data = await request.json()
    email = data.get('email', None)
    title = data.get('title', None)
    content = data.get('content', None)
    quantity = data.get('quantity', 1)
    date = data.get('date', None)
    place = data.get('place', None)
    if not title or not content or quantity is None:
        return web.json_response({"error": "Поля 'title' и 'content', и 'quantity' обязательны"}, status=400)

    service = {'id': next_id, 'user': email, 'title': title, 'content': 
               content, 'available': True, 'quantity': quantity,
               'date': date, 'place': place}
    services.append(service)
    next_id += 1
    return web.json_response(service, status=201)

async def get_services(request):
    available_param = request.rel_url.query.get('available')
    if available_param is not None:
        available = available_param.lower() == 'true'
        filtered = [service for service in services if service['available'] == available]
    else:
        filtered = services

    return web.json_response(filtered, status = 200)

async def search_services(request):
    place = request.rel_url.query.get('place')
    date_str = request.rel_url.query.get('date') 

    if not date_str or not place: 
        return web.json_response({"error": "Укажите 'date' и 'place'"}, status=400)
    
    try:
        search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return web.json_response({"error": "Неверный формат даты. Используйте YYYY-MM-DD"}, 
                                  status=400)
    try:
        filtered_services = [service for service in services
                             if service['place'] == place and service['date'] == search_date.isoformat()]

        return web.json_response(filtered_services, status=200)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def send_confirmation_email(booked_service, recipient_email):
    message = f"""Subject: Подтверждение бронирования услуги

    Вы успешно забронировали услугу: {booked_service['title']}
    Количество: {booked_service['quantity']}
    """
    
    smtp = aiosmtplib.SMTP(
        hostname=EMAIL_HOST,
        port=587  # Порт для STARTTLS
    )
    
    try:
        await smtp.connect()
        await smtp.starttls()  # Обновляем соединение до TLS
        await smtp.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        await smtp.sendmail(DEFAULT_FROM_EMAIL, [recipient_email], message)
    except Exception as e:
        print(f"Ошибка при отправке email: {e}")
    finally:
        await smtp.quit()  # Закрываем соединение

async def book_service(request):

   global services, next_id
   service_id = int(request.match_info['id'])
   data = await request.json()
   quantity_to_book = data.get('quantity_to_book', 1)
   email_that_booked = data.get('email_that_booked', None)
   for service in services:
    if service['id'] == service_id:
        if service['available'] and service['quantity'] >= quantity_to_book:
            booked_service = {
                'service_id': service['id'],
                'title': service['title'],
                'quantity': quantity_to_book
            }
            booked_services.append(booked_service)
            service['quantity'] -= quantity_to_book
            if service['quantity'] == 0:
                service['available'] = False
            asyncio.create_task(send_confirmation_email(booked_service, email_that_booked)) #нужно сделать аутентификацию
            return web.json_response(booked_service, status=200)
        
        else:
            return web.json_response({"error": "Услуга недоступна или недостаточное количество."}, status=400)
        
    return web.json_response({"error": "Услуга не найдена"}, status=404)
   
async def delete_booked_service(request):
    try:
        service_id = int(request.match_info['id'])
        global booked_services

        new_booked_services = [service for service in booked_services if service['service_id'] != service_id]

        if len(new_booked_services) == len(booked_services):
            return web.json_response({"error": "Бронь с указанным ID не найдена"}, status=404)

        booked_services = new_booked_services 

        return web.json_response({'success': 'Бронь отменена'}, status=204)

    except ValueError:
        return web.json_response({"error": "Неверный формат ID"}, status=400)
    except KeyError as e:
        return web.json_response({"error": f"Ключ не найден: {str(e)}"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500) 



app = web.Application()

app.add_routes([
    web.post('/create_services', create_service),
    web.get('/services', get_services),
    web.post('/services/{id}/book', book_service),
    web.post('/register', register),  # New route for registration
    web.post('/login', login),
    web.get('/users', get_users),
    web.get('/booked_services', get_booked_services),
    web.get('/search_services', search_services),
    web.delete('/delete_booked_service/{id}', delete_booked_service)

])

print(booked_services)

if __name__ == '__main__':
    web.run_app(app, host="127.0.0.1", port=8080)