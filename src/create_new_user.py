import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

supabase = create_client(supabase_url, supabase_key)

# Crear usuario NUEVO con email diferente
email = "admin@ventas.com"
password = "admin123456"

try:
    # Crear usuario
    user = supabase.auth.sign_up({
        "email": email,
        "password": password,
    })
    
    if user.user:
        print("✅ USUARIO CREADO EXITOSAMENTE:")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
        print("💡 Usa estas credenciales para hacer login")
    else:
        print("❌ Error creando usuario")
        
except Exception as e:
    print(f"❌ Error: {e}")
    # Intentar iniciar sesión por si ya existe
    try:
        user = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        print("✅ Usuario ya existe. Credenciales:")
        print(f"📧 Email: {email}")
        print(f"🔑 Password: {password}")
    except Exception as e2:
        print(f"❌ Error completo: {e2}")