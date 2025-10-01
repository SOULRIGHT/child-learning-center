print("Starting basic test...")

try:
    from app import app
    print("App imported successfully")
    
    with app.app_context():
        print("App context created")
        
        from app import db, Child, DailyPoints
        print("Models imported")
        
        gangseo = Child.query.filter_by(name='강서진').first()
        if gangseo:
            print(f"Found 강서진: {gangseo.cumulative_points} points")
        else:
            print("No 강서진 found")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Test complete")

