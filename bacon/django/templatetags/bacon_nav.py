from django import template
import django

register = template.Library()


@register.simple_tag
def widget(panel, widget):
    f = globals().get("render_%s" % widget.__class__.__name__, render_widget)
    return f(panel, widget)


def render_DatesRangeWidget(panel, widget):
    # build urls with placeholders
    urls = widget.get_urls(panel)

    # Current values for the widget
    value_from, value_to = panel.get_query().get_range(widget.axis)

    value_from = value_from.strftime("%d/%m/%Y") if value_from else ""
    value_to = value_to.strftime("%d/%m/%Y") if value_to else ""

    return render_widget(
        panel,
        widget,
        urls=urls,
        unique="bacon_dates_range_" + widget.axis,
        value_from=value_from,
        value_to=value_to,
    )


def render_StringFilterWidget(panel, widget):
    urls = widget.get_urls(panel)
    value = panel.get_query().get_filter(widget.axis, widget.op)
    return render_widget(
        panel,
        widget,
        urls=urls,
        value=value or "",
        unique="bacon_string_filter_{}".format(widget.axis),
    )


@register.inclusion_tag("bacon/nav/widgets/_button.tmpl")
def button(button, widget, panel):
    label = button.label
    url = button.get_url(widget, panel)
    image_url = button.image_url
    return {"label": label, "url": url, "image_url": image_url}


def render_widget(panel, widget, **kwargs):
    kwargs["panel"] = panel
    kwargs["widget"] = widget
    tmpl = "bacon/nav/widgets/%s.tmpl" % widget.__class__.__name__
    tmpl = template.loader.get_template(tmpl)
    if django.VERSION[:2] >= (1, 8):
        context = kwargs
    else:
        context = template.Context(kwargs)
    return tmpl.render(context)
