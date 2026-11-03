#!/bin/zsh
# Double-click in Finder: checks the setup, then processes the content calendar once.
cd "${0:A:h}"
./ce doctor
echo; echo "Processing the calendar..."; echo
./ce run
echo; echo "Done. Finished reels are in the ready/ folder. You can close this window."
open ready
