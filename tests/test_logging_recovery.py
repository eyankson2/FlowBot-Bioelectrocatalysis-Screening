"""Regression cases for ERROR.txt (Windows MAX_PATH / csv logger recursion)."""
import csv
import os
import tempfile
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fluidics import EventLogger, run_log_directory


class LoggingRecoveryTests(unittest.TestCase):
    def test_standard_csv_file_created_with_one_header(self):
        with TemporaryDirectory() as tmp:
            target=Path(tmp)/'logs'/'flowbot_umbrella_test.csv'
            gui=[]
            logger=EventLogger(gui.append,target)
            logger.log('Connecting dedicated gas controller...')
            logger.log('Gas connected')
            with target.open(newline='', encoding='utf-8') as f:
                rows=list(csv.reader(f))
            self.assertEqual(rows[0],['timestamp','thread','event'])
            self.assertEqual([row[2] for row in rows[1:]],
                             ['Connecting dedicated gas controller...', 'Gas connected'])
            self.assertEqual(len(gui),2)

    def test_failed_primary_location_recovers_to_short_local_csv(self):
        with TemporaryDirectory() as tmp:
            # This is a regular file, not a directory.  CSV creation must fail.
            broken_root=Path(tmp)/'inaccessible_parent'
            broken_root.write_text('file, not directory')
            bad_log=broken_root/'flowbot_umbrella_test.csv'
            fallback_root=Path(tmp)/'LOCALAPPDATA'/'FlowBot'/'Logs'
            display=[]
            with patch('fluidics.run_log_directory',return_value=fallback_root):
                with patch('fluidics.tempfile.gettempdir',return_value=str(Path(tmp)/'temp')):
                    logger=EventLogger(display.append,bad_log)
                    logger.log('Connecting dedicated gas controller...')
                    logger.log('Fluidics connected')
            self.assertEqual(logger.csv_path,fallback_root/bad_log.name)
            with logger.csv_path.open(newline='',encoding='utf-8') as f:
                data=list(csv.reader(f))
            self.assertEqual(data[0],['timestamp','thread','event'])
            self.assertEqual(len([r for r in data if r[-1]=='Connecting dedicated gas controller...']),1)
            self.assertEqual(len([r for r in data if r[-1]=='Fluidics connected']),1)
            self.assertTrue(any('redirected' in event for event in display))

    def test_all_disk_writes_fail_without_crashing_worker(self):
        events=[]
        logger=EventLogger(events.append,Path('flowbot_run.csv'))
        with patch.object(EventLogger,'_append_csv',side_effect=OSError('Simulated read-only disk')):
            thread=threading.Thread(target=lambda: [logger.log('Starting'),logger.log('Finished')])
            thread.start();thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(logger.csv_path)
        self.assertEqual(logger.csv_disabled_reason,'Simulated read-only disk')
        self.assertEqual(sum('CSV logging disabled' in event for event in events),1)
        self.assertTrue(any('Finished' in event for event in events))

    def test_default_directory_uses_localappdata_not_deep_onedrive_cwd(self):
        with TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{'LOCALAPPDATA':str(Path(tmp)/'AppData'/'Local')}):
                expected=Path(tmp)/'AppData'/'Local'/'FlowBot'/'Logs'
                self.assertEqual(run_log_directory(),expected)


if __name__=='__main__':
    unittest.main()
