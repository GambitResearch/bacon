from django.http import HttpResponse


def render_figure(request, fig):
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

    canvas = FigureCanvas(fig)
    return render_canvas(request, canvas)


def render_canvas(request, canvas):
    response = HttpResponse(content_type="image/png")
    canvas.print_png(response)
    return response
