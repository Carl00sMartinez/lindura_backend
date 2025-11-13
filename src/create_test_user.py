import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

supabase = create_client(supabase_url, supabase_key)

# Crear usuario de prueba
email = "test@ventas.com"
password = "test123456"

try:
    # Crear usuario
    user = supabase.auth.sign_up({
        "email": email,
        "password": password,
    })
    
    print("✅ Usuario creado:")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print("Guarda estas credenciales para probar el frontend")
    
except Exception as e:
    print(f"❌ Error creando usuario: {e}")
    # Si el usuario ya existe, intenta iniciar sesión para obtener token
    try:
        user = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        print("✅ Usuario ya existe, token obtenido:")
        print(f"Token: {user.session.access_token}")
    except Exception as e2:
        print(f"❌ Error: {e2}")