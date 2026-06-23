import os
import sys
import time
import re


from pfspeak.services import pfconfig, commandline_args
from pfspeak.tts.runtime import TextToSpeech

PATH_RE = re.compile(r'(~|/)\S+')

def serve() -> int:
    import sounddevice as sd
    try:
        fd = os.open(pfconfig.pipe_path, os.O_RDONLY | os.O_NONBLOCK)
    except Exception:
        sys.stderr.write("Could not get file descriptor\n")
        sys.exit(17)

    runtime = TextToSpeech()

    with open(fd, 'r') as fifo:

        backlog = []
        queue = []
        size = 0
              
        buffer = []
        stream = None

        try:

            print("System Ready...")

            RUN_FOREVER = True
            SHUTDOWN = False

            pfconfig.ready_file.touch(exist_ok=True)

            while RUN_FOREVER:
                if SHUTDOWN and not any([backlog, queue, buffer]):
                    sd.wait()
                    break

                time.sleep(pfconfig.latency)

                should_work = True
                if stream:
                    if not stream.active:
                        stream.close()
                        stream = None
                    if queue != []:
                        should_work = False

                # Play next audio in buffer if not already playing
                if buffer and not stream:
                    chunk = buffer.pop(0)
                    sd.play(chunk, samplerate=pfconfig.samplerate)
                    stream = sd.get_stream() 

                
                # Read lines, add them to the backlog. Also handles magic words
                for line in fifo:
                    line = line.strip()
                    if commandline_args.verbose:
                        print(line)

                    if line in ["$EXIT", "$BREAK"]:
                        if stream and stream.active:
                            stream.stop()
                        backlog = []
                        buffer = []
                        queue = []
                        size = 0

                    if line == "$EXIT":
                        RUN_FOREVER = False
                        break
                    elif line == "$SHUTDOWN":
                        SHUTDOWN = True
                        print('shutdown_requested')
                        continue
                    elif line == "$BREAK":
                        continue
                    if line == "$SKIP":
                        if stream and stream.active:
                            stream.stop()
                        continue

                    backlog.append(line)


                if backlog and queue == []:
                    max_size = pfconfig.queue_size

                    while backlog:
                        if size == 0 or size + len(backlog[0]) < max_size:
                            line = backlog.pop(0)
                            size += len(line)
                            queue.append(line)
                        else:
                            break


                # Generate audio from text the queue 
                if queue and should_work:
                    buffer.append(
                            runtime.speak(
                                PATH_RE.sub("path like", '\n'.join(queue)),
                                pfconfig.voice,
                                speed=pfconfig.speech_speed
                                ).waveform
                            )
                    queue = []
                    size = 0


        except KeyboardInterrupt:
            sys.stderr.write("\nshutdown requested\n")
            print('shutdown_requested')
            return 0
        except Exception as exc:
            print('unexpected_error')
            raise exc
        finally:
            pfconfig.ready_file.unlink(missing_ok=True)
            sd.stop()

    pfconfig.ready_file.unlink(missing_ok=True)
    sd.wait()
    sd.stop()
    return 0
