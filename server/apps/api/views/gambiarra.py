from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from apps.persistence.models.gallery import Album, Photo

@require_http_methods(["GET", "POST"])
def upload_photos(request):
    albums = Album.objects.all()

    if request.method == "POST":
        album_id = request.POST.get("album")
        files = request.FILES.getlist("images")

        if album_id and files:
            album = Album.objects.get(pk=album_id)

            for f in files:
                Photo.objects.create(
                    album=album,
                    image=f,
                    name=f.name
                )

            return redirect("api:upload_photos")  # ou outra rota

    return render(request, "upload_photos.html", {
        "albums": albums
    })