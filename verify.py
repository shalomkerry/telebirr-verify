from tele import verify_telebirr_transaction
from fastapi import FastAPI,Request,HTTPException

from fastapi import FastAPI, Request, HTTPException
from tele import verify_telebirr_transaction  # Import your actual verification function

app = FastAPI()

# Define your verification function
def verify(message, expected_amount=6, expected_receiver='Shalom Badeg Shalemo'):
    try:
        result = verify_telebirr_transaction(
            message,
            expected_amount=expected_amount,
            expected_receiver=expected_receiver,
            return_data=True
        )

        if isinstance(result, tuple) and len(result) == 3:
            is_valid, msg, data = result
        elif isinstance(result, tuple) and len(result) == 2:
            is_valid, msg = result
            data = {}
        else:
            is_valid = False
            msg = "Unknown return format"
            data = {}

    except Exception as e:
        is_valid = False
        msg = f"Error during verification: {str(e)}"
        data = {}

    return is_valid, msg, data

@app.post("/verify")
async def verify_endpoint(req: Request):
    # Parse JSON body
    try:
        body = await req.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    # Extract message
    message = body.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' in request")
    
    # Extract optional parameters
    expected_amount = body.get("expected_amount", 6)
    expected_receiver = body.get("expected_receiver", 'Shalom Badeg Shalemo')
    
    # Call your verify function
    is_valid, msg, data = verify(
        message,
        expected_amount=expected_amount,
        expected_receiver=expected_receiver
    )
    
    return {
        "is_valid": is_valid,
        "msg": msg,
        "data": data
    }

# Add root endpoint for health checks
@app.get("/")
def health_check():
    return {"status": "running", "service": "telebirr-verification"}

