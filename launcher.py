import sys
import os
import multiprocessing
import traceback
import threading
import webbrowser
import time

# Essential for PyInstaller + Multiprocessing to prevent infinite loops
multiprocessing.freeze_support()

def main():
    try:
        # Adjust working directory to executable path to ensure assets are found
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            os.chdir(base_dir)
            sys.path.append(base_dir)
        
        print("--------------------------------------------------")
        print("   TIF Inventory Application - Standalone Loader")
        print("--------------------------------------------------")
        print("Loading application logic...")
        
        # Ensure MongoDB auth backend is selected BEFORE flask_app is imported
        # (auth_flask._select_auth_backend() runs at module import time)
        os.environ.setdefault('DB_BACKEND', 'mongodb')
        
        # Import the app and helpers from the main flask_app
        # This must be done AFTER changing the working directory
        from flask_app import app, initialize_runtime_directories
        
        print("Initializing runtime environments...")
        initialize_runtime_directories()
        
        # Initialize performance optimizations
        try:
            from utils.performance_optimization import initialize_performance_optimizations
            success, message = initialize_performance_optimizations()
            if success:
                print(f"Performance Check: {message}")
            else:
                print(f"Performance Warning: {message}")
        except ImportError:
            print("Performance module not found, skipping.")
        except Exception as e:
            print(f"Error initializing performance optimizations: {e}")
            
        def open_browser():
            """Open the browser after a short delay to ensure server is running"""
            time.sleep(2)
            print("Launching web browser...")
            webbrowser.open('http://127.0.0.1:5000')
            
        print("Starting web server on http://127.0.0.1:5000")
        print("Keep this window open while using the application.")
        print("--------------------------------------------------")
        
        # Start browser launcher in background
        threading.Thread(target=open_browser, daemon=True).start()
        
        # Run Flask app
        # IMPORTANT: debug=False is required for frozen apps.
        # Bind to loopback by default (item 1.10). Network exposure requires
        # explicit opt-in via ALLOW_NETWORK_ACCESS=true (or FLASK_HOST=0.0.0.0).
        host = os.environ.get('FLASK_HOST')
        if not host:
            if os.environ.get('ALLOW_NETWORK_ACCESS', 'false').lower() == 'true':
                host = '0.0.0.0'
            else:
                host = '127.0.0.1'
        port = int(os.environ.get('FLASK_PORT', '5000'))
        app.run(host=host, port=port, debug=False)
        
    except Exception as e:
        print("\n!!!!!!!!!!!!!! CRITICAL ERROR !!!!!!!!!!!!!!")
        print("The application failed to start.")
        print(f"Error details: {e}\n")
        traceback.print_exc()
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    finally:
        print("\nApplication execution finished.")
        # Pause to let user read any errors
        if sys.platform == 'win32':
             os.system('pause')
        else:
             input("Press Enter to close window...")

if __name__ == '__main__':
    main()
