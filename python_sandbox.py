import os
import tempfile
import subprocess
import logging

log = logging.getLogger("jarvis.sandbox")

def run_python_code(code: str) -> str:
    """
    Executes a Python code string in a temporary file and returns the standard output.
    Used by JARVIS to perform complex math, data analysis, and logic verification.
    """
    try:
        # Create a temporary file
        fd, path = tempfile.mkstemp(suffix=".py", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(code)
            
        log.info(f"Executing Python Sandbox code in {path}")
        
        # Run the script with a 10-second timeout
        result = subprocess.run(
            ["python3", path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Clean up
        os.remove(path)
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if result.returncode != 0:
            return f"Error de ejecución:\n{error}"
            
        if not output:
            return "Código ejecutado con éxito, pero no produjo ninguna salida (stdout)."
            
        return f"Resultado de la ejecución:\n{output}"
        
    except subprocess.TimeoutExpired:
        os.remove(path)
        return "Error: La ejecución del código excedió el tiempo límite de 10 segundos."
    except Exception as e:
        log.error(f"Sandbox error: {e}")
        return f"Error del sistema Sandbox: {e}"
