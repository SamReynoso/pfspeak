import sys
from pfspeak.app import pfconfig
from pfspeak.cli.parser import parser
from pfspeak.app.listen import listen


args = parser.parse_args()


if __name__ == "__main__":

    if args.command == "verify":
        sys.exit(1)

    elif args.command == "worker":
        from pfspeak.core.runtime.worker import worker
        exit(worker(args.host, args.port))

    elif args.command == "config":
        from pfspeak.cli.messages import config_output
        print(config_output)

    elif args.command == "install":
        from pfspeak.app.install import install
        install(pfconfig)

    elif args.command == "listen":
        listen()

    elif args.command == "speak":
        from pfspeak.app.speak import serve
        sys.exit(serve())

    elif args.command == "test":
        ...

    elif args.command == "import-check":
        ...

    else:
        parser.print_help()
        sys.exit(1)
