from hmt_stock_check import parse_cards

# Plain HTML as it looks AFTER json.loads() has already decoded \/ -> /
# (this is exactly what parse_cards() receives in production, since
# resp.json() does that decoding for us automatically)
SAMPLE_OOS = """
<div class="col-lg-4 col-md-6 col-sm-6 col-xs-12 mb-3 p-0">
    <div class="bc_p_item" >
        <a target="_blank" href = "https://www.hmtwatches.in/product_overview?id=ABC123" class="bc_p_img">
        <img src="https://www.hmtwatches.in/storage/app/public/image/all_images/2810251252461001.jpg" class />
        </a>
        <div class="bc_p_detail">
            <a target="_blank" href="https://www.hmtwatches.in/product_overview?id=DEF456" class="bc_p_name">
            <span> HMT Pilot Automati..</span>
            </a>
            <p>RS. 18499</p>
             <div class="outofstock"><p class="vote text-danger" style="color: red;"><strong>Coming Soon</strong></p></div>
        </div>
        <div class="col-12 down_scroll">
            <div class="inner_down_scroll">
                <div class="inner_down_scroll_top">
                    <div class="inner_down_scroll_top_left" data-toggle="tooltip" data-original-title="Notify Me">
                        <span class="pointer" onclick="notifyMe(1154)"><i class="fa fa-shopping-cart"></i></span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

SAMPLE_IN_STOCK = """
<div class="col-lg-4 col-md-6 col-sm-6 col-xs-12 mb-3 p-0">
    <div class="bc_p_item" >
        <a target="_blank" href = "https://www.hmtwatches.in/product_overview?id=XYZ789" class="bc_p_img">
        <img src="https://www.hmtwatches.in/storage/app/public/image/all_images/9999999999.jpg" class />
        </a>
        <div class="bc_p_detail">
            <a target="_blank" href="https://www.hmtwatches.in/product_overview?id=QQQ111" class="bc_p_name">
            <span> HMT Test Watch In Stock..</span>
            </a>
            <p>RS. 9999</p>
        </div>
        <div class="col-12 down_scroll">
            <div class="inner_down_scroll">
                <div class="inner_down_scroll_top">
                    <div class="inner_down_scroll_top_left" data-toggle="tooltip" data-original-title="Notify Me">
                        <span class="pointer" onclick="notifyMe(9999)"><i class="fa fa-shopping-cart"></i></span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

html = SAMPLE_OOS + SAMPLE_IN_STOCK
products = parse_cards(html)

for p in products:
    print(p)

assert len(products) == 2, f"Expected 2 cards, got {len(products)}"
assert products[0]["in_stock"] is False, "First card should be OUT of stock"
assert products[1]["in_stock"] is True, "Second card should be IN stock"
assert products[0]["id"] == "1154"
assert products[1]["id"] == "9999"
assert products[0]["price"] == "18499"
assert products[1]["price"] == "9999"
assert "HMT Pilot Automati" in products[0]["name"]
assert "HMT Test Watch In Stock" in products[1]["name"]
assert products[0]["image"].endswith("2810251252461001.jpg")
assert products[0]["url"].startswith("https://www.hmtwatches.in/product_overview?id=ABC123")
print("\nAll assertions passed.")
