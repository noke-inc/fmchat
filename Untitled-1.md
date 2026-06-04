2026-06-04T11:07:59 | INFO     | agent.agent | Running agent for message: 'how many units?'
2026-06-04T11:07:59 | INFO     | langchain_aws.chat_models.bedrock_converse | Using Bedrock Converse API to generate response
2026-06-04T11:07:59 | INFO     | botocore.tokens | Loading cached SSO token for Janus
ERROR:    Exception in ASGI application
  + Exception Group Traceback (most recent call last):
  |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\_utils.py", line 77, in collapse_excgroups
  |     yield
  |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\base.py", line 186, in __call__
  |     async with anyio.create_task_group() as task_group:
  |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\anyio\_backends\_asyncio.py", line 799, in __aexit__
  |     raise BaseExceptionGroup(
  | ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
  +-+---------------- 1 ----------------
    | Traceback (most recent call last):
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\uvicorn\protocols\http\httptools_impl.py", line 421, in run_asgi
    |     result = await app(  # type: ignore[func-returns-value]
    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\uvicorn\middleware\proxy_headers.py", line 63, in __call__
    |     return await self.app(scope, receive, send)
    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\fastapi\applications.py", line 1054, in __call__
    |     await super().__call__(scope, receive, send)
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\applications.py", line 113, in __call__
    |     await self.middleware_stack(scope, receive, send)
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\errors.py", line 187, in __call__
    |     raise exc
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\errors.py", line 165, in __call__
    |     await self.app(scope, receive, _send)
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\base.py", line 185, in __call__
    |     with collapse_excgroups():
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\contextlib.py", line 158, in __exit__
    |     self.gen.throw(typ, value, traceback)
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\_utils.py", line 83, in collapse_excgroups
    |     raise exc
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\base.py", line 188, in __call__
    |     await response(scope, wrapped_receive, send)
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\base.py", line 222, in __call__
    |     async for chunk in self.body_iterator:
    |   File "C:\Users\pradesh.kumar\python\3.11\Lib\site-packages\starlette\middleware\base.py", line 171, in body_stream
    |     assert message["type"] == "http.response.body"
    |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    | AssertionError
    +------------------------------------