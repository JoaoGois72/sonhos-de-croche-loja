PACOTE ULTRA PROFISSIONAL DA LOJA

Arquivos incluídos:
- templates/base.html
- templates/index.html
- templates/admin_login.html
- templates/admin_dashboard.html
- templates/admin_encomendas.html
- templates/admin_products.html
- templates/admin_product_form.html
- templates/product_detail.html
- static/css/premium.css

Observações importantes:
1. O pacote presume que seu app.py já tenha rotas equivalentes para:
   - index
   - cart_view
   - admin_login / admin_login_post / admin_logout / admin_dashboard
   - admin_encomendas / admin_encomenda_status / admin_encomenda_delete
   - admin_products / admin_product_new ou admin_products_new
   - admin_product_edit ou admin_products_edit
   - product_detail
   - custom_order (ou /encomendas)

2. Para a seção Instagram ficar bonita, adicione:
   static/img/insta1.jpg
   static/img/insta2.jpg
   static/img/insta3.jpg
   static/img/insta4.jpg

3. Se suas imagens de produto estiverem em Cloudinary, as URLs funcionam direto.
   Se estiverem locais, os templates já suportam static/uploads.

4. Se o navegador não refletir as mudanças, use Ctrl + Shift + R.
