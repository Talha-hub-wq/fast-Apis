from fastapi import FastAPI,Path, HTTPException,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Annotated , Literal ### use description add

class Patient(BaseModel):
    id: Annotated[int,Field(...,description="id of the patient", example="id=1")]
    name: Annotated[str, Field(..., description="name of the patient")] 
    age: Annotated[int, Field(..., gt=0,lt=60, description="age of the patient")] 
    gender :Annotated[Literal['male', 'female', 'other'],Field(..., description = "gender of the patient")]
    dignosis: Annotated[str , Field(..., description="dignosis of the patient")]
    admitted: Annotated[bool , Field(..., description="admitted status of the patient")]


import json

## craete an object of FastAPI
app = FastAPI()
##json file read fr python dictionary
def data_load():
    with open("patient.json", "r") as f:
        return json.load(f)  # loads as Python list
## json file save
def save_data(data):
    with open ('patient.json','w') as f:
        json.dump(data,f)


##/ route  GET endpoint build .

@app.get("/")
def hello():
    return {"message": "the patient management system"}
##/about route  GET endpoint build.
@app.get("/about")
def about():
    return {
        "message": "the patient management system is a web application that allows healthcare providers to manage patient information, appointments, and medical records efficiently."
    }
### view all  endpoint
@app.get('/view')
def view():
    return data_load()

## create new endpoint to view a specific patient by ID
@app.get('/patient/{patient_id}')
def view_patient(patient_id: int = Path(..., description="id of the patient", example="id=1")):  # integer type
    data = data_load()
    for patient in data:
        if patient["id"] == patient_id:
            return patient
    raise HTTPException(status_code=404, detail='patient not found')

## 
@app.get('/sort')
def sort_patient(sort_by: str, order: str = 'asc'):
    data = data_load()
    print("Loaded data:", data)  # check if data is correct

    if order not in ['asc', 'desc']:
        raise HTTPException(status_code=400, detail='order must be asc or desc')

    if sort_by not in data[0]:
        raise HTTPException(status_code=400, detail=f"'{sort_by}' not found in patient data")

    reverse = (order == 'desc')
    sorted_data = sorted(data, key=lambda x: x[sort_by], reverse=reverse)
    print("Sorted data:", sorted_data)  # check the result

    return sorted_data
### use pydantic model

@app.post("/create")
def create_patient(patient: Patient):
    # Load data
    data = data_load()

    # Check if patient already exists
    for p in data:
        if p["id"] == patient.id:
            raise HTTPException(status_code=400, detail="Patient already exists")

    # Add new patient
    data.append(patient.dict())

    # Save data
    save_data(data)

    # ✅ Return must be indented inside the function
    return JSONResponse(
        status_code=201,
        content={"patient": "patient load successfully"}
    )


