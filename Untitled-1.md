Under auth folder - i have copied the code which was created for the authorize. Re use this code and update it accordingly and tell me how we can test in local - also i will deploy in AWS. 

for chat:
  → Portal frontend calls MCP /api/ai/chat (with Authorization: Bearer <NOKE_JWT>)
  → MCP proxies to Q Business
  → Q Business OAuth challenge → MCP handles it
  → Returns AI answer

  Download all the required dependecies and check the build is working.