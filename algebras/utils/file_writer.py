import queue
import threading
from typing import Dict, Optional

from algebras.utils.ts_handler import write_ts_translation_file_in_place


class IncrementalFileWriter:
    """
    Thread-safe incremental file writer that processes write operations sequentially
    using a queue to ensure file consistency.
    """

    def __init__(
        self, file_path: str, file_type: str, export_name: Optional[str] = None
    ):
        """
        Initialize incremental file writer.

        Args:
            file_path: Path to the file to write
            file_type: Type of file ('ts', 'json', etc.)
            export_name: Export name for TypeScript files
        """
        self.file_path = file_path
        self.file_type = file_type
        self.export_name = export_name
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self.writer_thread.start()
        self.error_occurred = False
        self.error_message = None

    def write_batch(self, translations: Dict[str, str], batch_index: int):
        """
        Add batch results to write queue.

        Args:
            translations: Dictionary of key -> translation to write
            batch_index: Index of the batch (for logging)
        """
        self.queue.put(("write", translations, batch_index))

    def finish(self):
        """
        Signal that no more batches will be added and wait for all writes to complete.
        """
        # Signal that we're done adding items
        self.queue.put(("finish", None, None))
        # Wait for writer thread to finish
        self.writer_thread.join(timeout=60)  # 60 second timeout
        if self.writer_thread.is_alive():
            print(f"  ⚠ Warning: Writer thread did not finish in time")
        if self.error_occurred:
            raise Exception(
                f"Error writing to file {self.file_path}: {self.error_message}"
            )

    def _writer_loop(self):
        """Process write queue sequentially."""
        while True:
            try:
                # Get next item from queue (blocks until available)
                item_type, translations, batch_index = self.queue.get(timeout=1)

                if item_type == "finish":
                    # Signal to finish
                    break
                elif item_type == "write":
                    # Write batch results to file
                    try:
                        if self.file_type == "ts":
                            write_ts_translation_file_in_place(
                                self.file_path,
                                translations,
                                self.export_name,
                                self.lock,
                            )
                        # Add support for other file types here if needed
                        else:
                            print(
                                f"  ⚠ Warning: Incremental write not supported for {self.file_type} files"
                            )
                    except Exception as e:
                        self.error_occurred = True
                        self.error_message = str(e)
                        print(
                            f"  ✗ Error writing batch {batch_index} to {self.file_path}: {str(e)}"
                        )

                # Mark task as done
                self.queue.task_done()
            except queue.Empty:
                # Timeout - check if we should continue
                continue
            except Exception as e:
                self.error_occurred = True
                self.error_message = str(e)
                print(f"  ✗ Error in writer loop: {str(e)}")
                break
