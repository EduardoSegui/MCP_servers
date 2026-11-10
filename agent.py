import asyncio
import json # <-- NUEVO IMPORT
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import AsyncClient

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
    )

    print("Iniciando conexión con el servidor MCP...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            tools_response = await session.list_tools()
            mcp_tools = tools_response.tools
            print(f"Herramientas MCP descubiertas: {[t.name for t in mcp_tools]}")

            ollama_tools = []
            for t in mcp_tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema
                    }
                })

            client = AsyncClient()
            modelo = "qwen2.5-coder:7b" 
            
            mensajes = [{
                "role": "user", 
                "content": "Por favor, usa la herramienta disponible para revisar los 30 primeros libros más vendidos de Cúspide y actualizar mi CSV."
            }]
            
            print(f"\nConsultando al agente local ({modelo})...")
            response = await client.chat(
                model=modelo,
                messages=mensajes,
                tools=ollama_tools
            )

            # 5. Interceptar la decisión del modelo (Manejando ambos casos)
            if response.message.tool_calls:
                # Caso A: El modelo usó la API nativa de herramientas
                for tool_call in response.message.tool_calls:
                    print(f"\n[Agente] Ejecutando herramienta (Nativo): {tool_call.function.name}")
                    
                    result = await session.call_tool(
                        tool_call.function.name,
                        tool_call.function.arguments
                    )
                    print(f"\n[MCP Server Responde] -> {result.content[0].text}")
            
            else:
                # Caso B: El modelo escribió el JSON como texto (Fallback)
                contenido = response.message.content.strip()
                try:
                    # Intentamos leer el texto como si fuera un JSON
                    llamada_manual = json.loads(contenido)
                    
                    # Verificamos que tenga la estructura de una herramienta
                    if "name" in llamada_manual and "arguments" in llamada_manual:
                        print(f"\n[Agente] Ejecutando herramienta (Parseo de Texto JSON): {llamada_manual['name']}")
                        
                        result = await session.call_tool(
                            llamada_manual["name"],
                            llamada_manual["arguments"]
                        )
                        print(f"\n[MCP Server Responde] -> {result.content[0].text}")
                    else:
                        print("\n[Agente] El modelo respondió directamente:")
                        print(contenido)
                
                except json.JSONDecodeError:
                    # Si falla, significa que realmente respondió con texto normal
                    print("\n[Agente] El modelo respondió directamente sin usar herramientas:")
                    print(contenido)

if __name__ == "__main__":
    asyncio.run(main())