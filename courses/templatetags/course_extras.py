from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using its key.
    Usage: {{ dictionary|get_item:key }}
    """
    return dictionary.get(key)

@register.filter
def attr(obj, attr_name):
    """
    Get an attribute of an object safely.
    Usage: {{ object|attr:'attribute_name' }}
    """
    if obj is None:
        return None
    
    try:
        return getattr(obj, attr_name)
    except (AttributeError, TypeError):
        return None 