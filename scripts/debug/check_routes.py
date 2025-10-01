from app import app
 
print("등록된 Flask 라우트들:")
for rule in app.url_map.iter_rules():
    print(f"{rule.rule} -> {rule.endpoint}") 