from django.contrib import admin
from .models import Tag, Category, Articles, ArticleTag, ArticlesVersion, ArticleImage


class ArticleTagInline(admin.TabularInline):
    model = ArticleTag
    extra = 1


class ArticlesVersionInline(admin.StackedInline):
    model = ArticlesVersion
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


class ArticleImageInline(admin.TabularInline):
    model = ArticleImage
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Articles)
class ArticlesAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'visibility', 'status', 'created_at', 'updated_at')
    list_filter = ('visibility', 'status', 'category')
    search_fields = ('title', 'description')
    inlines = [ArticleTagInline, ArticlesVersionInline, ArticleImageInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(ArticlesVersion)
class ArticlesVersionAdmin(admin.ModelAdmin):
    list_display = ('article', 'product_version', 'status', 'author', 'reviewed_by', 'created_at')
    list_filter = ('status', 'product_version')
    search_fields = ('article__title', 'content', 'changes')


@admin.register(ArticleImage)
class ArticleImageAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'article', 'article_version', 'file_size', 'mime_type', 'uploaded_by')
    search_fields = ('file_name', 'alt_text', 'caption')