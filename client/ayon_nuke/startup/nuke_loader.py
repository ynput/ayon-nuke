import os
import platform
import subprocess
import json
from ayon_core.pipeline import get_current_project_name
from ayon_core.settings import get_project_settings

class AyonNukeLauncher:
    
    def __init__(self, logger=None):
        self.project_name = get_current_project_name()
        self.settings = get_project_settings(self.project_name)
        self.current_platform = self._get_current_platform()
        self.log = logger  # Store the logger
    
    def _log(self, level, message):
        """Internal logging method that uses passed logger or falls back to print."""
        if self.log:
            getattr(self.log, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def _get_current_platform(self):
        """Get current platform in AYON format."""
        system = platform.system().lower()
        platform_map = {
            'windows': 'windows',
            'linux': 'linux',
            'darwin': 'darwin'
        }
        return platform_map.get(system)
    
    def get_available_nuke_variants(self, app_name='nuke'):
        """Get all available Nuke variants."""
        applications = self.settings['applications']['applications']
        
        if app_name not in applications:
            raise RuntimeError(f"Application '{app_name}' not found in AYON settings")
        
        app_config = applications[app_name]
        variants = app_config.get('variants', [])
        
        available_variants = []
        
        for variant in variants:
            variant_name = variant.get('name')
            variant_label = variant.get('label', variant_name)
            executables = variant.get('executables', {})
            
            if self.current_platform in executables:
                platform_executables = executables[self.current_platform]
                
                if platform_executables and len(platform_executables) > 0:
                    executable_path = platform_executables[0]
                    
                    if os.path.exists(executable_path):
                        available_variants.append({
                            'name': variant_name,
                            'label': variant_label,
                            'executable': executable_path,
                            'arguments': variant.get('arguments', {}).get(self.current_platform, []),
                            'environment': variant.get('environment', '{}')
                        })
        
        return available_variants
    
    def get_nuke_executable(self, app_name='nuke', variant_name=None):
        """Get Nuke executable for specific variant."""
        variants = self.get_available_nuke_variants(app_name)
        
        if not variants:
            raise RuntimeError(f"No working {app_name} variants found for {self.current_platform}")
        
        if variant_name is None:
            selected_variant = variants[0]
            self._log('info', f"Using default {app_name} variant: {selected_variant['label']}")
        else:
            selected_variant = None
            for variant in variants:
                if variant['name'] == variant_name:
                    selected_variant = variant
                    break
            
            if not selected_variant:
                available_names = [v['name'] for v in variants]
                raise RuntimeError(f"Variant '{variant_name}' not found. Available: {available_names}")
        
        return selected_variant
    
    def _setup_environment(self, environment_json):
        """Setup environment variables from variant config."""
        env = os.environ.copy()
        
        # Add AYON context
        env.update({
            'AYON_PROJECT_NAME': self.project_name,
        })
        
        # Parse and add variant-specific environment
        try:
            if environment_json:
                variant_env = json.loads(environment_json)
                for key, value in variant_env.items():
                    if isinstance(value, list):
                        separator = ';' if self.current_platform == 'windows' else ':'
                        existing_value = env.get(key, '')
                        if existing_value:
                            env[key] = separator.join([existing_value] + value)
                        else:
                            env[key] = separator.join(value)
                    else:
                        env[key] = str(value)
        except json.JSONDecodeError as e:
            self._log('warning', f"Could not parse environment JSON: {e}")
        
        return env
    
    def execute_python_code(self, python_code, app_name='nuke', variant_name=None, verbose=True):
        """Execute Python code directly in Nuke using -c flag."""
        
        variant_config = self.get_nuke_executable(app_name, variant_name)
        executable = variant_config['executable']
        arguments = variant_config['arguments']
        environment_json = variant_config['environment']
        
        if verbose:
            self._log('info', f"Executing Python code in {app_name} {variant_config['label']}")
            self._log('debug', f"Executable: {executable}")
        
        # Build command with -c flag
        cmd = [executable]
        cmd.extend(arguments)
        cmd.extend(["-t", "-c", python_code])
        
        env = self._setup_environment(environment_json)
        
        if verbose:
            self._log('debug', f"Command: {' '.join(cmd[:3])} [PYTHON_CODE]")
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if verbose:
                self._log('debug', f"Return code: {result.returncode}")
                if result.stdout:
                    self._log('info', f"Nuke output: {result.stdout}")
                if result.stderr:
                    self._log('warning', f"Nuke stderr: {result.stderr}")
            
            success = result.returncode == 0
            if success:
                self._log('info', "✓ Nuke execution successful")
            else:
                self._log('error', f"✗ Nuke execution failed with code {result.returncode}")
            
            return success, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            self._log('error', "✗ Nuke execution timed out")
            return False, "", "Timeout"
        except Exception as e:
            self._log('error', f"✗ Error launching Nuke: {e}")
            return False, "", str(e)
    
    def execute_python_interactive(self, python_code, app_name='nuke', variant_name=None, verbose=True):
        """Execute Python code via stdin (interactive mode)."""
        
        variant_config = self.get_nuke_executable(app_name, variant_name)
        executable = variant_config['executable']
        arguments = variant_config['arguments']
        environment_json = variant_config['environment']
        
        if verbose:
            self._log('info', f"Executing Python code interactively in {app_name} {variant_config['label']}")
        
        # Build command for interactive mode
        cmd = [executable]
        cmd.extend(arguments)
        cmd.append("-t")
        
        env = self._setup_environment(environment_json)
        
        # Add exit command to ensure clean shutdown
        code_with_exit = python_code + '\nnuke.scriptExit()\n'
        
        try:
            result = subprocess.run(
                cmd,
                input=code_with_exit,
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if verbose:
                self._log('debug', f"Return code: {result.returncode}")
                if result.stdout:
                    self._log('info', f"Nuke output: {result.stdout}")
                if result.stderr:
                    self._log('warning', f"Nuke stderr: {result.stderr}")
            
            success = result.returncode == 0
            if success:
                self._log('info', "✓ Nuke interactive execution successful")
            else:
                self._log('error', f"✗ Nuke interactive execution failed with code {result.returncode}")
            
            return success, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            self._log('error', "✗ Nuke execution timed out")
            return False, "", "Timeout"
        except Exception as e:
            self._log('error', f"✗ Error launching Nuke: {e}")
            return False, "", str(e)
    
    def execute_python_file(self, script_path, app_name='nuke', variant_name=None, verbose=True):
        """Execute Python file in Nuke using -x flag."""
        
        variant_config = self.get_nuke_executable(app_name, variant_name)
        executable = variant_config['executable']
        arguments = variant_config['arguments']
        environment_json = variant_config['environment']
        
        if verbose:
            self._log('info', f"Executing Python file in {app_name} {variant_config['label']}")
            self._log('debug', f"Script: {script_path}")
        
        # Build command with -x flag
        cmd = [executable]
        cmd.extend(arguments)
        cmd.extend(["-t", "-x", script_path])
        
        env = self._setup_environment(environment_json)
        
        if verbose:
            self._log('debug', f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if verbose:
                self._log('debug', f"Return code: {result.returncode}")
                if result.stdout:
                    self._log('info', f"Nuke output: {result.stdout}")
                if result.stderr:
                    self._log('warning', f"Nuke stderr: {result.stderr}")
            
            success = result.returncode == 0
            if success:
                self._log('info', "✓ Nuke file execution successful")
            else:
                self._log('error', f"✗ Nuke file execution failed with code {result.returncode}")
            
            return success, result.stdout, result.stderr
                
        except subprocess.TimeoutExpired:
            self._log('error', "✗ Nuke execution timed out")
            return False, "", "Timeout"
        except Exception as e:
            self._log('error', f"✗ Error launching Nuke: {e}")
            return False, "", str(e)