# AWS Cost Explorer Agent (Strands + MCP + Lambda)

This project demonstrates how to build a **real-time AWS Cost Explorer Agent** using the **Strands Framework**, **Model Context Protocol (MCP)**, and **AWS Lambda**.


<img width="1024" height="1536" alt="ChatGPT Image Oct 1, 2025, 12_17_18 AM" src="https://github.com/user-attachments/assets/b364e2be-ebfd-4d3f-9139-39dcc80e4cbb" />

Ask questions in plain English, like:
- "What is my spend from 2025-09-01 to 2025-10-01?"
- "Forecast my spend from 2025-10-01 to 2025-11-01"

And get both structured JSON + a plain-English summary.

---

## 🚀 Architecture

1. **Client** → Sends a query via API Gateway or Lambda Function URL  
2. **AWS Lambda** → Runs the Strands Agent  
3. **MCP Cost Server** → Calls AWS Cost Explorer APIs (`GetCostAndUsage`, `GetCostForecast`)  
4. **Amazon Bedrock** → Converts raw data into natural-language summaries  
5. **Response** → JSON with `tool_data` and `summary`

---

## 📦 Setup

### 1. Clone repo
```bash
git clone https://github.com/<your-username>/aws-cost-agent-strands.git
cd aws-cost-agent-strands
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Local test
```bash
python -c "from agent import handle; print(handle('What is my spend from 2025-09-01 to 2025-10-01?'))"
```

---

## 🚀 Deployment (Windows with Batch Script)

This project includes a ready-to-use batch file for deploying the Lambda function and setting up API Gateway.

### 1. Prerequisites
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured  
- Python 3.11  
- IAM role with permissions for:  
  - `ce:GetCostAndUsage`  
  - `ce:GetCostForecast`  
  - `bedrock:InvokeModel`  
  - `logs:*`  
  - `lambda:*`  
  - `apigateway:*`  

### 2. Package the code
Zip up the function code (already structured for Lambda):
```bat
powershell -Command "Compress-Archive -Path * -DestinationPath function.zip -Force"
```

### 3. Run the deploy script
```bat
deploy-cost-agent.bat
```

The script will:
1. Create or update the IAM role (`lambda-cost-agent-role`).
2. Deploy/update the Lambda function (`cost-agent`).
3. Configure environment variables for Bedrock + Cost Explorer.
4. Create or update an API Gateway endpoint.
5. Output the API Gateway URL for testing.

### 4. Test the endpoint
Once deployed, you can test with `curl` or Postman:
```bat
curl -X POST "https://<api-id>.execute-api.us-east-1.amazonaws.com/" ^
 -H "Content-Type: application/json" ^
 -d "{\"query\":\"What is my spend from 2025-09-01 to 2025-10-01?\"}"
```

You’ll get back JSON like this:
```json
{
  "tool_data": {
    "currency": "USD",
    "total": 17.40,
    "period": { "start": "2025-09-01", "end": "2025-10-01" },
    "grouped": [
      { "service": "Amazon Cognito", "amount": 15.59, "unit": "USD" }
    ]
  },
  "summary": "Most of your spend (~90%) is from Cognito. Tax and EC2 are small. Others are negligible."
}
```

---

<img width="1024" height="1024" alt="ChatGPT Image Sep 30, 2025, 11_44_26 PM" src="https://github.com/user-attachments/assets/cda55feb-e0b4-49d9-a7ca-2e5e1b85bbb4" />
<img width="1026" height="761" alt="Screenshot 2025-09-30 234216" src="https://github.com/user-attachments/assets/a37dcde5-f2fb-43d5-b6d9-6c4dee42bbb7" />

## 🗑️ Cleaning Up (delete-cost-agent.bat)

If you want to **remove all deployed resources** (API Gateway, Lambda function, CloudWatch log group, and IAM role), 
you can use the provided cleanup script:

```powershell
delete-cost-agent.bat
```

This script will:
1. Find and delete any API Gateway named `cost-agent-api` (handles multiple IDs safely).
2. Delete the Lambda function `cost-agent` and its Function URL (if present).
3. Delete the associated CloudWatch log group.
4. Detach policies and remove the IAM role `lambda-cost-agent-role`.

⚠️ **Warning**: This will permanently delete the resources. Make sure nothing else depends on this role or function.


## 📖 References
- [AWS Strands Blog](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

## 📝 License
MIT
