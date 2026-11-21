from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
import re

register = template.Library()


@register.filter
def mentionize(text):
    escaped = escape(text)
    return mark_safe(re.sub(r'@([A-Za-z0-9_]{3,30})', r'<span class="mention">@\1</span>', escaped))


@register.simple_tag(takes_context=True)
def modify_query(context, **kwargs):
    """Собирает querystring с изменёнными параметрами (для пагинации с фильтрами)."""
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
