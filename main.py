import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema

app = FastAPI(title="Clothing Store API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class ObjectIdStr(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):  # type: ignore
        # simple passthrough for pydantic v2 typing compatibility
        return _handler(str)

def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Convert nested ObjectIds if any
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
    return d


@app.get("/")
def read_root():
    return {"message": "Clothing Store Backend is running"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Products API
class ProductResponse(BaseModel):
    id: ObjectIdStr
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
    image: Optional[str] = None


@app.get("/api/products", response_model=List[ProductResponse])
def list_products(category: Optional[str] = None):
    filter_q = {"category": category} if category else {}
    docs = get_documents("product", filter_q)
    return [serialize_doc(d) for d in docs]


@app.post("/api/products", status_code=201)
def create_product(product: ProductSchema):
    try:
        data = product.model_dump()
        # Allow optional image
        if "image" not in data:
            data["image"] = None
        inserted_id = create_document("product", data)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: str):
    try:
        from pymongo import ReturnDocument
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Product not found")
        return serialize_doc(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")


@app.get("/api/categories", response_model=List[str])
def list_categories():
    if db is None:
        return []
    cats = db["product"].distinct("category")
    return sorted([c for c in cats if c])


@app.post("/api/seed", tags=["dev"])  # simple seeding endpoint for demo
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    count = db["product"].count_documents({})
    if count > 0:
        return {"inserted": 0, "message": "Products already exist"}
    demo = [
        {
            "title": "Essential Tee",
            "description": "Ultra-soft cotton tee with a relaxed fit.",
            "price": 24.00,
            "category": "Tops",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1520975922215-c994c6a8dffd?q=80&w=1200&auto=format&fit=crop"
        },
        {
            "title": "Everyday Hoodie",
            "description": "Cozy fleece hoodie for all-day comfort.",
            "price": 58.00,
            "category": "Hoodies",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?q=80&w=1200&auto=format&fit=crop"
        },
        {
            "title": "Slim Chinos",
            "description": "Tailored chinos with stretch for movement.",
            "price": 64.00,
            "category": "Bottoms",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1520975916090-3105956dac38?q=80&w=1200&auto=format&fit=crop"
        },
        {
            "title": "Classic Denim Jacket",
            "description": "Timeless denim with a modern wash.",
            "price": 89.00,
            "category": "Outerwear",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1520975693416-35b05b6cb4f2?q=80&w=1200&auto=format&fit=crop"
        },
        {
            "title": "Athletic Joggers",
            "description": "Lightweight joggers for lounge or gym.",
            "price": 49.00,
            "category": "Bottoms",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?q=80&w=1200&auto=format&fit=crop"
        }
    ]
    inserted = db["product"].insert_many(demo).inserted_ids
    return {"inserted": len(inserted)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
