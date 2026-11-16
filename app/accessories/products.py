CATEGORIES = {
    "proteccion": "Protección",
    "seguridad": "Seguridad y ruta",
    "equipamiento": "Tecnología y equipaje",
    "mantenimiento": "Mantenimiento",
}

SIZES = {
    "casco-integral": ("S", "M", "L", "XL"),
    "casco-modular": ("S", "M", "L", "XL"),
    "guantes": ("S", "M", "L", "XL"),
    "chaqueta": ("S", "M", "L", "XL"),
    "botas": ("39", "40", "41", "42", "43"),
    "impermeable": ("M", "L", "XL"),
}

COMPATIBILITY = {
    "soporte-celular": "Confirma el diámetro del manillar y las dimensiones de tu teléfono antes de comprar.",
    "baul": "Requiere un portaequipaje compatible con la base del baúl. Comprueba el anclaje de tu moto.",
    "cargador-usb": "Comprueba el voltaje disponible y el espacio en el manillar antes de instalarlo.",
    "candado-disco": "Comprueba el diámetro y el espacio libre en los orificios del disco.",
    "caballete": "Comprueba el ancho del basculante y el tipo de apoyo que usa tu moto.",
}

# sku, nombre, categoría, descripción, precio COP y stock inicial de demostración.
PRODUCTS = (
    ("casco-integral", "Casco integral mate", "proteccion", "Visera transparente y acabado grafito.", 289900, 12),
    ("casco-modular", "Casco modular gris", "proteccion", "Mentón abatible y visera transparente.", 389900, 8),
    ("guantes", "Guantes reforzados", "proteccion", "Protecciones en los nudillos y cierre ajustable.", 79900, 22),
    ("chaqueta", "Chaqueta de moto ventilada", "proteccion", "Paneles de ventilación para trayectos urbanos.", 249900, 10),
    ("botas", "Botas de moto urbanas", "proteccion", "Botas de caña baja con puntera reforzada.", 219900, 9),
    ("impermeable", "Traje impermeable", "proteccion", "Chaqueta y pantalón para llevar bajo el asiento.", 94900, 16),
    ("candado-disco", "Candado de disco", "seguridad", "Incluye cable recordatorio de alta visibilidad.", 69900, 20),
    ("cadena", "Cadena de seguridad", "seguridad", "Cadena recubierta con candado incluido.", 119900, 14),
    ("compresor", "Compresor portátil", "seguridad", "Inflador compacto con indicador de presión.", 149900, 11),
    ("kit-pinchazos", "Kit antipinchazos", "seguridad", "Herramientas y mechas para neumáticos sin cámara.", 45900, 25),
    ("funda", "Funda impermeable", "seguridad", "Cubierta para estacionar la moto a la intemperie.", 74900, 18),
    ("botiquin", "Botiquín compacto", "seguridad", "Estuche de primeros auxilios para llevar en ruta.", 39900, 17),
    ("soporte-celular", "Soporte para celular", "equipamiento", "Montaje ajustable para el manillar.", 64900, 21),
    ("intercomunicador", "Intercomunicador para casco", "equipamiento", "Unidad compacta con micrófono para el casco.", 189900, 7),
    ("cargador-usb", "Cargador USB para moto", "equipamiento", "Dos puertos con tapa para protegerlos del polvo.", 59900, 19),
    ("baul", "Baúl trasero rígido", "equipamiento", "Compartimento de carga con cierre y base de montaje.", 229900, 8),
    ("bolso-tanque", "Bolso magnético de tanque", "equipamiento", "Bolso compacto para objetos de uso frecuente.", 99900, 13),
    ("alforjas", "Alforjas blandas", "equipamiento", "Par de bolsos laterales para equipaje ligero.", 179900, 6),
    ("kit-cadena", "Kit de cuidado de cadena", "mantenimiento", "Limpiador, lubricante y cepillo para la transmisión.", 82900, 15),
    ("caballete", "Caballete trasero", "mantenimiento", "Soporte para mantenimiento con la moto detenida.", 139900, 8),
)
