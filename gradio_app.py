import gradio as gr  
import os  
import json  
import base64  
from dotenv import load_dotenv  
from io import BytesIO  
from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient  
from msrest.authentication import ApiKeyCredentials  
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches 
  
# Load environment variables  
load_dotenv()  
  
# Azure OpenAI client initialization  
from openai import AzureOpenAI  
client = AzureOpenAI(  
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
    api_version="2024-02-01",  
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")  
)  
  
# Custom Vision configuration  
CUSTOM_VISION_ENDPOINT = os.getenv("CUSTOM_VISION_ENDPOINT")  
CUSTOM_VISION_KEY = os.getenv("CUSTOM_VISION_PREDICTION_KEY")  
CUSTOM_VISION_PROJECT_ID = os.getenv("CUSTOM_VISION_PROJECT_ID")  
CUSTOM_VISION_MODEL_NAME = os.getenv("CUSTOM_VISION_MODEL_NAME")  
  
# Prediction client  
prediction_credentials = ApiKeyCredentials(in_headers={"Prediction-key": CUSTOM_VISION_KEY})  
predictor = CustomVisionPredictionClient(CUSTOM_VISION_ENDPOINT, prediction_credentials)  
  
prediction_threshold = 0.4  
  
def open_image_to_base64(image):  
    buffered = BytesIO()  
    image.save(buffered, format="JPEG")  
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")  
    base64_url = f"data:image/jpeg;base64,{img_str}"  
    return base64_url  
  
def analyze_logo(compliance_prompt, image_1, client):  
    response = client.chat.completions.create(  
        model=os.getenv("AZURE_OPENAI_MODEL"),  
        response_format={"type": "json_object"},  
        messages=[  
            {  
                "role": "user",  
                "content": [  
                    {"type": "text", "text": compliance_prompt},  
                    {  
                        "type": "image_url",  
                        "image_url": {  
                            "url": image_1,  
                            "detail": "high"  
                        },  
                    }  
                ],  
            }  
        ],  
        max_tokens=300,  
    )  
    return response.choices[0]  
  
def requirements_lookup(logo_name):  
    with open("logo_requirements.json", "r") as json_file:  
        data = json.load(json_file)  
    return data[logo_name]  
  
def generate_compliance_prompt(requirements):  
    return f'''You are a creative designer assistant tasked with ensuring logos are compliant with the brand.  
You are presented with an image of a logo and a list of requirements that can be used to check whether a logo is compliant with the brand.  
  
# Analyze the logo and determine if it is compliant with the brand.  
# You must ignore anything that is around the logo like text etc. You must focus on the logo only  
  
## Important: the logo can be rotated, flipped or in any orientation, a flipped logo is still compliant if it meets the requirements  
  
# You must consider the following questions when analyzing the logo:  
{requirements}  
  
# Answer each question with True or False  
# If any answer is False, the logo is not compliant  
  
## Your response should be a JSON with the following structure:  
{{"compliant":True, "explanation":"summary of the explanation", "questions": "answers to each question"}}  
'''  
  
def detect_and_analyze_logo(image_file):  
    # Convert the image to bytes and run prediction
    
    image_contents = BytesIO()
    image_file.save(image_contents, format="JPEG")
    image_contents = image_contents.getvalue()
    results = predictor.detect_image(CUSTOM_VISION_PROJECT_ID, CUSTOM_VISION_MODEL_NAME, image_contents)
      
    analysis_results = []  
    
     # Generate HTML table
    fig, ax = plt.subplots(1)

    ax.imshow(image_file)

    # Add bounding boxes
    for prediction in results.predictions:
        if prediction.probability > prediction_threshold:

            rect = patches.Rectangle(
                (prediction.bounding_box.left * image_file.width, prediction.bounding_box.top * image_file.height),
                prediction.bounding_box.width * image_file.width,
                prediction.bounding_box.height * image_file.height,
                linewidth=2, edgecolor='g', facecolor='none'
            )
            ax.add_patch(rect)
            plt.text(
                prediction.bounding_box.left * image_file.width,
                prediction.bounding_box.top * image_file.height - 10,
                f"{prediction.tag_name}: {prediction.probability:.2f}",
                color='green', fontsize=12, weight='bold'
            )

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plot_image = Image.open(buf)

    for prediction in results.predictions:  
        if prediction.probability > prediction_threshold:  
            buffered = BytesIO()  
  
            left = max(0, int(prediction.bounding_box.left * image_file.width))  
            top = max(0, int(prediction.bounding_box.top * image_file.height))  
            right = min(image_file.width, int((prediction.bounding_box.left + prediction.bounding_box.width) * image_file.width))  
            bottom = min(image_file.height, int((prediction.bounding_box.top + prediction.bounding_box.height) * image_file.height))  
  
            cropped_image = image_file.crop((left, top, right, bottom))  
            cropped_image.convert('RGB').save(buffered, format="JPEG")  
  
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")  
            base64_url = f"data:image/jpeg;base64,{img_str}"  
  
            reqs = requirements_lookup(prediction.tag_name)  
            compliance_prompt = generate_compliance_prompt(reqs)  
  
            try:  
                logo_compliance = analyze_logo(compliance_prompt, base64_url, client).message.content  
                compliance_dict = json.loads(logo_compliance)  
                compliance_dict["logo_name"] = prediction.tag_name  
                compliance_list = [f"![]({base64_url})", json.dumps(compliance_dict)]
                analysis_results.append(compliance_list)  
               
            except Exception as e:  
                print(e)  
                continue  
  
  
    return [plot_image, analysis_results]
  
gr.Interface(  
    fn=detect_and_analyze_logo,  
    inputs=gr.components.Image(type="pil", label="Upload an Image"),  
    outputs=[gr.Image(label="Logo Detection"), gr.components.DataFrame(headers=["Extracted Logo","Compliance"],
                                    label="logo Compliance", 
                                    datatype="markdown")] ,
    allow_flagging="never",
    title="Azure AI Logo Compliance Checker",
).launch()    