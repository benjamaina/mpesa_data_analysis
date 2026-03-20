from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "mpesa analyzer is online....."}


@app.get("/upload")
async def get_data():
    try:
        # code to get data from the user and store it in the database
        return {"message": "data received successfully"}
    except Exception as e:
        return {"message": f"an error occurred: {str(e)}"}