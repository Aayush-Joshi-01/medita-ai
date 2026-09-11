"""Placeholder worker process.

The `worker` compose service runs this module so the container has something
to do and stays up. It is replaced by a real arq worker (job queue consuming
`analyze_image`, `transcribe`, `analyze_transcript`, `ingest_document`,
`fhir_sync` tasks — see docs/architecture.md section 5) in build step 3.
"""

import time


def main() -> None:
    print("medita-ai worker stub running — arq task consumer lands in build step 3.", flush=True)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
