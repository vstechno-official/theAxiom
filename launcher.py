import os
import sys
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

    if getattr(sys, 'frozen', False):
        os.environ['AXIOM_FROZEN'] = '1'
        db_path = os.path.join(base_dir, 'db.sqlite3')
        if not os.path.exists(db_path):
            import django
            django.setup()
            from django.core.management import call_command
            call_command('migrate', '--run-syncdb', verbosity=0)
        else:
            import django
            django.setup()
            from django.core.management import call_command
            call_command('migrate', verbosity=0)
    else:
        import django
        django.setup()

    from django.core.management import call_command

    def open_browser():
        time.sleep(2)
        webbrowser.open('http://127.0.0.1:8000/')

    if '--no-browser' not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()

    call_command('runserver', '127.0.0.1:8000', '--noreload', use_reloader=False)


if __name__ == '__main__':
    main()