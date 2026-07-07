import sys
from pfspeak.app import pfconfig
from pfspeak.cli.parser import parser
from pfspeak.extra.examples import EXAMPLES


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

    elif args.command == "examples":
        EXAMPLES[args.example].main()

    elif args.command == "import-check":
        ...

    elif args.command == "daemon":
        from pfspeak.app.daemon import main
        main()


    else:
        parser.print_help()
        sys.exit(1)
