# A Axiom entity ;)
# A Axiom entity ;)
import os
import sys
import io
import webbrowser
import threading
import time


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    base_dir = get_base_dir()
    os.chdir(base_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'axiom.settings')

    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')

    if getattr(sys, 'frozen', False):
        os.environ['AXIOM_FROZEN'] = '1'

    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', verbosity=0)

    def open_browser():
        time.sleep(2.5)
        webbrowser.open('http://127.0.0.1:8765/')

    if '--no-browser' not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()

    from django.core.management.commands.runserver import Command as RunServer
    RunServer.stdout = sys.stdout
    RunServer.stderr = sys.stderr

    call_command('runserver', '127.0.0.1:8765', '--noreload')


if __name__ == '__main__':
    main()
