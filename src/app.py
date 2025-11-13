import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import traceback

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurar CORS de manera más permisiva para desarrollo
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)

# Configuración Supabase
try:
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        logger.error("❌ Faltan variables de entorno SUPABASE_URL o SUPABASE_KEY")
        supabase = None
    else:
        supabase: Client = create_client(supabase_url, supabase_key)
        logger.info("✅ Cliente Supabase inicializado correctamente")
        
except Exception as e:
    logger.error(f"❌ Error inicializando Supabase: {e}")
    supabase = None

# Manejar requests OPTIONS para CORS
@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        return response

# ==================== MIDDLEWARE DE AUTENTICACIÓN ====================
def check_auth():
    """Verifica que el usuario esté autenticado"""
    auth_header = request.headers.get('Authorization')
    logger.info(f"🔐 Header de autorización recibido: {auth_header}")
    
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.warning("❌ No se proporcionó token de autorización")
        return None
    
    token = auth_header.replace('Bearer ', '')
    
    try:
        user = supabase.auth.get_user(token)
        if user and user.user:
            logger.info(f"✅ Usuario autenticado: {user.user.email}")
            return user.user
        logger.warning("❌ Token inválido o usuario no encontrado")
        return None
    except Exception as e:
        logger.error(f"❌ Error de autenticación: {e}")
        return None

# ==================== ENDPOINTS PÚBLICOS (SIN AUTENTICACIÓN) ====================

@app.route('/')
def home():
    return jsonify({
        "message": "🚀 API de Ventas Personal funcionando!",
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "supabase_connected": supabase is not None
    })

@app.route('/api/health')
def health_check():
    try:
        if supabase is None:
            return jsonify({
                "status": "degraded",
                "database": "disconnected - configura Supabase",
                "timestamp": datetime.now().isoformat()
            }), 200
            
        response = supabase.table('products').select('id').limit(1).execute()
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 500

# ==================== ENDPOINTS DE PRODUCTOS ====================

@app.route('/api/products', methods=['GET'])
def get_products():
    """Obtener todos los productos del usuario"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        response = supabase.table('products')\
            .select('*')\
            .eq('user_id', user.id)\
            .order('created_at', desc=True)\
            .execute()
        
        # Verificar productos con stock bajo
        products = response.data
        for product in products:
            product['low_stock'] = product['stock'] <= product.get('low_stock_alert', 5)
        
        return jsonify(products)
    except Exception as e:
        logger.error(f"Error obteniendo productos: {e}")
        return jsonify({'error': 'Error obteniendo productos'}), 500

@app.route('/api/products', methods=['POST'])
def create_product():
    """Crear un nuevo producto"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        logger.info(f"📦 Creando producto: {data}")
        
        # Validaciones básicas
        if not data.get('name') or not data.get('price'):
            return jsonify({'error': 'Nombre y precio son requeridos'}), 400
        
        product_data = {
            'name': data['name'],
            'price': float(data['price']),
            'stock': int(data.get('stock', 0)),
            'category': data.get('category', ''),
            'low_stock_alert': int(data.get('low_stock_alert', 5)),
            'user_id': user.id
        }
        
        response = supabase.table('products').insert(product_data).execute()
        
        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({'error': 'Error creando producto'}), 400
            
    except Exception as e:
        logger.error(f"Error creando producto: {e}")
        return jsonify({'error': 'Error creando producto'}), 500

@app.route('/api/products/<product_id>', methods=['PUT'])
def update_product(product_id):
    """Actualizar un producto existente"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        # Verificar que el producto pertenece al usuario
        existing_product = supabase.table('products')\
            .select('*')\
            .eq('id', product_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if not existing_product.data:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        # Preparar datos para actualizar
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'price' in data:
            update_data['price'] = float(data['price'])
        if 'stock' in data:
            update_data['stock'] = int(data['stock'])
        if 'category' in data:
            update_data['category'] = data['category']
        if 'low_stock_alert' in data:
            update_data['low_stock_alert'] = int(data['low_stock_alert'])
        
        response = supabase.table('products')\
            .update(update_data)\
            .eq('id', product_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({'error': 'Error actualizando producto'}), 400
            
    except Exception as e:
        logger.error(f"Error actualizando producto: {e}")
        return jsonify({'error': 'Error actualizando producto'}), 500

@app.route('/api/products/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Eliminar un producto"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Verificar que el producto pertenece al usuario
        existing_product = supabase.table('products')\
            .select('*')\
            .eq('id', product_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if not existing_product.data:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        response = supabase.table('products')\
            .delete()\
            .eq('id', product_id)\
            .eq('user_id', user.id)\
            .execute()
        
        return jsonify({'message': 'Producto eliminado correctamente'})
        
    except Exception as e:
        logger.error(f"Error eliminando producto: {e}")
        return jsonify({'error': 'Error eliminando producto'}), 500

# ==================== ENDPOINTS DE VENTAS ====================

@app.route('/api/sales', methods=['POST'])
def create_sale():
    """Registrar una nueva venta - VERSIÓN MEJORADA"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        logger.info(f"💰 Creando venta: {data}")
        
        # Validaciones básicas
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'error': 'La venta debe tener al menos un item'}), 400
        
        # Calcular total y verificar stock
        total = 0
        items_to_process = []
        
        for item in data['items']:
            if not item.get('product_id') or not item.get('quantity'):
                return jsonify({'error': 'Cada item debe tener product_id y quantity'}), 400
            
            # Verificar stock disponible
            product_response = supabase.table('products')\
                .select('id, name, stock, price')\
                .eq('id', item['product_id'])\
                .eq('user_id', user.id)\
                .execute()
            
            if not product_response.data:
                return jsonify({'error': f"Producto {item['product_id']} no encontrado"}), 404
            
            product = product_response.data[0]
            if product['stock'] < item['quantity']:
                return jsonify({'error': f"Stock insuficiente para {product['name']}. Stock disponible: {product['stock']}"}), 400
            
            item_price = item.get('unit_price', product['price'])
            total += item_price * item['quantity']
            
            # Guardar información del producto para procesar después
            items_to_process.append({
                'product': product,
                'item_data': item,
                'unit_price': item_price
            })
        
        # Crear la venta
        sale_data = {
            'total': total,
            'customer_id': data.get('customer_id') or None,  # Asegurar que sea NULL si está vacío
            'user_id': user.id
        }
        
        logger.info(f"📝 Creando venta con datos: {sale_data}")
        sale_response = supabase.table('sales').insert(sale_data).execute()
        
        if not sale_response.data:
            logger.error("❌ Error creando la venta en la base de datos")
            return jsonify({'error': 'Error creando la venta en la base de datos'}), 400
        
        sale_id = sale_response.data[0]['id']
        logger.info(f"✅ Venta creada con ID: {sale_id}")
        
        # Crear items de venta y actualizar stock
        for item_info in items_to_process:
            product = item_info['product']
            item_data = item_info['item_data']
            unit_price = item_info['unit_price']
            
            # Crear item de venta
            sale_item_data = {
                'sale_id': sale_id,
                'product_id': item_data['product_id'],
                'quantity': item_data['quantity'],
                'unit_price': unit_price
            }
            
            logger.info(f"📦 Creando item de venta: {sale_item_data}")
            item_response = supabase.table('sale_items').insert(sale_item_data).execute()
            
            if not item_response.data:
                logger.error(f"❌ Error creando item para producto {product['id']}")
                # Si falla un item, revertir la venta
                supabase.table('sales').delete().eq('id', sale_id).execute()
                return jsonify({'error': f"Error creando item para {product['name']}"}), 400
            
            # Actualizar stock del producto
            new_stock = product['stock'] - item_data['quantity']
            logger.info(f"🔄 Actualizando stock de {product['name']}: {product['stock']} -> {new_stock}")
            
            update_response = supabase.table('products')\
                .update({'stock': new_stock})\
                .eq('id', product['id'])\
                .execute()
            
            if not update_response.data:
                logger.error(f"❌ Error actualizando stock para {product['name']}")
                # Revertir la venta si falla la actualización de stock
                supabase.table('sales').delete().eq('id', sale_id).execute()
                supabase.table('sale_items').delete().eq('sale_id', sale_id).execute()
                return jsonify({'error': f"Error actualizando stock para {product['name']}"}), 400
        
        logger.info(f"✅ Venta {sale_id} completada exitosamente")
        return jsonify(sale_response.data[0])
        
    except Exception as e:
        logger.error(f"❌ Error creando venta: {str(e)}")
        logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/sales', methods=['GET'])
def get_sales():
    """Obtener todas las ventas del usuario"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        response = supabase.table('sales')\
            .select('*, sale_items(*, products(*)), customers(*)')\
            .eq('user_id', user.id)\
            .order('sale_date', desc=True)\
            .execute()
        
        return jsonify(response.data)
    except Exception as e:
        logger.error(f"Error obteniendo ventas: {e}")
        return jsonify({'error': 'Error obteniendo ventas'}), 500

# ==================== ENDPOINTS DE CLIENTES ====================

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Obtener todos los clientes del usuario"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        response = supabase.table('customers')\
            .select('*')\
            .eq('user_id', user.id)\
            .order('created_at', desc=True)\
            .execute()
        
        return jsonify(response.data)
    except Exception as e:
        logger.error(f"Error obteniendo clientes: {e}")
        return jsonify({'error': 'Error obteniendo clientes'}), 500

@app.route('/api/customers', methods=['POST'])
def create_customer():
    """Crear un nuevo cliente"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'El nombre es requerido'}), 400
        
        customer_data = {
            'name': data['name'],
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'user_id': user.id
        }
        
        response = supabase.table('customers').insert(customer_data).execute()
        
        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({'error': 'Error creando cliente'}), 400
            
    except Exception as e:
        logger.error(f"Error creando cliente: {e}")
        return jsonify({'error': 'Error creando cliente'}), 500

# ==================== ENDPOINTS DE REPORTES ====================

@app.route('/api/reports/daily-sales')
def daily_sales():
    """Obtener ventas del día actual"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        response = supabase.table('sales')\
            .select('*, sale_items(*)')\
            .eq('user_id', user.id)\
            .gte('sale_date', f'{date_str} 00:00:00')\
            .lte('sale_date', f'{date_str} 23:59:59')\
            .execute()
        
        return jsonify(response.data)
    except Exception as e:
        logger.error(f"Error obteniendo ventas diarias: {e}")
        return jsonify({'error': 'Error obteniendo ventas diarias'}), 500

# ==================== ENDPOINTS DE UTILIDAD ====================

@app.route('/api/backup', methods=['GET'])
def backup_data():
    """Exportar todos los datos del usuario"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        tables = ['products', 'customers', 'sales']
        backup = {}
        
        for table in tables:
            response = supabase.table(table)\
                .select('*')\
                .eq('user_id', user.id)\
                .execute()
            backup[table] = response.data
        
        return jsonify(backup)
    except Exception as e:
        logger.error(f"Error creando backup: {e}")
        return jsonify({'error': 'Error creando backup'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info("=" * 50)
    logger.info("🚀 INICIANDO SERVIDOR FLASK")
    logger.info(f"📍 Puerto: {port}")
    logger.info(f"🐛 Debug: {debug_mode}")
    logger.info(f"🔗 Supabase: {'✅ Conectado' if supabase else '❌ No conectado'}")
    logger.info("=" * 50)
    
    app.run(debug=debug_mode, port=port, host='0.0.0.0')

# ==================== ENDPOINTS DE CLIENTES (COMPLETOS) ====================

@app.route('/api/customers/<customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """Actualizar un cliente existente"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        
        # Verificar que el cliente pertenece al usuario
        existing_customer = supabase.table('customers')\
            .select('*')\
            .eq('id', customer_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if not existing_customer.data:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'email' in data:
            update_data['email'] = data['email']
        if 'phone' in data:
            update_data['phone'] = data['phone']
        
        response = supabase.table('customers')\
            .update(update_data)\
            .eq('id', customer_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({'error': 'Error actualizando cliente'}), 400
            
    except Exception as e:
        logger.error(f"Error actualizando cliente: {e}")
        return jsonify({'error': 'Error actualizando cliente'}), 500

@app.route('/api/customers/<customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """Eliminar un cliente"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Verificar que el cliente pertenece al usuario
        existing_customer = supabase.table('customers')\
            .select('*')\
            .eq('id', customer_id)\
            .eq('user_id', user.id)\
            .execute()
        
        if not existing_customer.data:
            return jsonify({'error': 'Cliente no encontrado'}), 404
        
        response = supabase.table('customers')\
            .delete()\
            .eq('id', customer_id)\
            .eq('user_id', user.id)\
            .execute()
        
        return jsonify({'message': 'Cliente eliminado correctamente'})
        
    except Exception as e:
        logger.error(f"Error eliminando cliente: {e}")
        return jsonify({'error': 'Error eliminando cliente'}), 500

# ==================== ENDPOINT DE REPORTES DE PRODUCTOS MÁS VENDIDOS ====================

@app.route('/api/reports/top-products')
def top_products():
    """Obtener productos más vendidos"""
    user = check_auth()
    if not user:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        # Consulta para obtener productos más vendidos
        response = supabase.table('sale_items')\
            .select('quantity, unit_price, products(name)')\
            .eq('sales.user_id', user.id)\
            .execute()
        
        # Procesar datos para agrupar por producto
        product_sales = {}
        for item in response.data:
            product_name = item['products']['name'] if item['products'] else 'Producto desconocido'
            if product_name not in product_sales:
                product_sales[product_name] = {
                    'quantity': 0,
                    'revenue': 0
                }
            product_sales[product_name]['quantity'] += item['quantity']
            product_sales[product_name]['revenue'] += item['quantity'] * item['unit_price']
        
        # Convertir a lista y ordenar por cantidad
        top_products_list = [
            {
                'name': name,
                'quantity': data['quantity'],
                'revenue': data['revenue']
            }
            for name, data in product_sales.items()
        ]
        top_products_list.sort(key=lambda x: x['quantity'], reverse=True)
        
        return jsonify(top_products_list[:10])  # Top 10 productos
        
    except Exception as e:
        logger.error(f"Error obteniendo productos más vendidos: {e}")
        return jsonify({'error': 'Error obteniendo reporte'}), 500
