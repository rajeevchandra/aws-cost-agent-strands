# Strands + MCP Cost Explorer (Bedrock) — Lambda ZIP



This gives you:
- `mcp_cost_server_safe.py`: MCP-style server calling AWS Cost Explorer (summary + forecast)
- `bedrock_model.py`: provider-aware Bedrock wrapper (works with `openai.gpt-oss-120b-1:0` or Anthropic if enabled)
- `agent.py`: tiny agent that calls the MCP server, then summarizes with Bedrock
- `strands_integration.py`: a **Strands-like** shim so you can mimic a Strands agent locally
- `lambda_handler.py`: deploy behind API Gateway or Function URL

- <img width="1024" height="1536" alt="ChatGPT Image Oct 1, 2025, 12_17_18 AM" src="https://github.com/user-attachments/assets/ed450e42-2690-4df6-b8c6-862b963668c0" />


## Local test (Windows CMD)
```
set AWS_REGION=us-east-1
set AWS_DEFAULT_REGION=us-east-1
set BEDROCK_REGION=us-east-1
set BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0 ( Any model)
set MCP_COMMAND=python mcp_cost_server_safe.py
set GROUP_BY=SERVICE,LINKED_ACCOUNT
set METRIC=UnblendedCost

python -c "from agent import handle; print(handle('What is my spend from 2025-09-01 to 2025-10-01?'))"
```

## Strands-style entry (shim)
```
python -c "from strands_integration import run_with_strands_like_agent as r; print(r('What is my spend from 2025-09-01 to 2025-10-01?'))"
```

## Real Strands integration (when you install their SDK)
```python
from strands.agents import Agent
from strands.tools.mcp import MCPToolClient

cost_tool = MCPToolClient(name="cost", transport="stdio", command=["python","mcp_cost_server_safe.py"])
agent = Agent(name="finops", tools=[cost_tool], instructions="You are an AWS cost assistant.")
agent.run("What is my spend from 2025-09-01 to 2025-10-01?")
```

## Lambda deploy
- Runtime: Python 3.11
- Handler: `lambda_handler.lambda_handler`
- Env: `BEDROCK_REGION`, `BEDROCK_MODEL_ID`, `MCP_COMMAND=python mcp_cost_server_safe.py` (+ optional `GROUP_BY`, `METRIC`, `GRANULARITY`)
- IAM: `bedrock:InvokeModel*`, `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ce:GetDimensionValues`

- <img width="1024" height="1024" alt="ChatGPT Image Sep 30, 2025, 11_44_26 PM" src="https://github.com/user-attachments/assets/6dafd886-ee44-4ccf-b29a-64cb28797c06" />


<img width="1026" height="761" alt="Screenshot 2025-09-30 234216" src="https://github.com/user-attachments/assets/51c292dd-46f2-4892-9ecd-623f38c3a595" />

