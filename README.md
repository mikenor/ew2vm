EW2VM
=====

Send EasyWorship song lyrics to vMix *Title* input
<https://github.com/mikenor/ew2vm>

About
-----

EW2VM is a hacked-together Python program that connects to the (unoffical) "remote control app" API of EasyWorship presentation software and retrieves slide text, which it transmits to a *Title* input in vMix video production software via the vMix API. This allows, for example, tastefully overlaying song lyrics from EasyWorship in a vMix-based livestream for remote participants, while leaving the main EasyWorship output free for displaying immersive fullscreen visuals to participants gathered in person.

This program will update the text of the vMix *Title* whenever the slide presented in EasyWorship is changed. The *Title*'s textboxes will be hidden whenever the EasyWorship output is set to `Logo`, `Black` or `Clear`.

__Because this program is critically dependent on unsupported use of an undocumented proprietary API for its core functionality, it should be considered highly experimental at all times.__ Please consider supporting [a feature request for an official EasyWorship API](https://support.easyworship.com/support/discussions/topics/6000033648).

Requirements
------------

### EW2VM requirements

EW2VM is written in Python 3. __You need Python >= 3.7 on the computer running EW2VM.__ Latest is appropriate. <https://www.python.org/downloads/>

__You need _dnspython_.__ To install on Windows, for example:

    py.exe -m pip install dnspython

On Windows, it is also __recommended to have _colorama___ so you can see coloured text in the console output. Without it, EW2VM will work but the console output will be ugly on Windows.

    py.exe -m pip install colorama 

### vMix requirements

EW2VM is designed for vMix 23 and subsequent versions supporting the vMix TCP API.

__You need a *Title* input with two textboxes.__ EW2VM will use one textbox for the slide text and one textbox for title/credits.

### EasyWorship requirements

EW2VM is experimentally functional with EasyWorship Build 7.2.3.0 running on Windows 10.

In the `Advanced` `Options` of EasyWorship, the __`Enable Remote Control` checkbox must be enabled__. This adds a `Remote` button on the main toolbar. From the `Remote` dropdown, remote control must be switched `On`. This should give you a __green dot on the toolbar button__.

Please test that your environment is compatible with EasyWorship remote control by using the official mobile app according to supported procedures.

Usage
-----

EW2VM can be executed on the same computer as EasyWorship, or on the same computer as vMix or on an independent computer. If running on a different machine from either program, then the other machine(s) must be specified on the command line by network address (computer name or IP).

The vMix input number, specified by `--vm-input NUM`, is mandatory.

When launched, EW2VM will attempt to connect to both programs endlessly. To exit, press CTRL+C.

__The first time connecting to EasyWorship, you must `Pair` with EW2VM in the `Remote` dropdown of the EasyWorship toolbar to allow communication.__

Examples:

    ew2vm.py --vm-host 192.168.1.23 --vm-input 12
    ew2vm.py --vm-host VIDEOPC --vm-input 12
    ew2vm.py --ew-host LYRICSPC --vm-host VIDEOPC --vm-input 12
    ew2vm.py --ew-host 192.168.1.55 --vm-input 12

### Command-line interface

From `--help`:

```
usage: ew2vm.py --vm-input NUM [options] | --help

Sends text from EasyWorship presentation/song slides to a vMix Title input using the TCP APIs of both programs.

optional arguments:
  -h, --help            show this help message and exit
  --ew-host HOST        network address where EasyWorship is running (default ::1)
  --ew-client-id GUID   client ID for connection to EasyWorship (e.g. if running multiple instances of ew2vm.py simultaneously)
  --vm-host HOST        network address where vMix is running (default ::1)
  --vm-input NUM        vMix input number
  --vm-textbox INDEX    textbox on vMix Title in which to place main slide text (default 0)
  --vm-textbox-credit INDEX
                        textbox on vMix Title in which to place title/credit text (default 1)
  --presentation-filter TAG [TAG ...]
                        only show presentations/songs that contain any slide with any TAG in the slide title
  --credit-slide TAG [TAG ...]
                        use the text from slide with any TAG in its title as custom title/credit text for the whole presentation/song (default "Title" "Credit" "Credits")

EW2VM Copyright (c) 2021 Michael Norton. MIT License; see LICENSE.md file for details.
```

Presentation filtering
----------------------

The `--presentation-filter TAG` argument allows you to send only certain presentations/songs to vMix. EW2VM will ignore presentations/songs that do not have any `TAG` in the title of at least one slide. Multiple `TAG`s can be specified by separating with space.

Examples:

    --presentation-filter Verse Chorus Bridge
    --presentation-filter "#streamready"
    --presentation-filter "#streamable" "#showthis"

If `--presentation-filter` is not specified, then EW2VM attempts to use the text of all slides presented.

Multiple instances
------------------

If you wish to simultaneously connect multiple instances of EW2VM to a single instance of EasyWorship, then you must specify a unique client GUID for each instance of EW2VM using the `--ew-client-id GUID` argument. `GUID` can be arbitrary as long as it is valid form and is unique among running instances.

Each unique ID will appear as a new device in EasyWorship. You must `Pair` from the `Remote` dropdown of the EasyWorship toolbar to allow communication.

Examples:

    --ew-client-id af519bbb-36b5-4661-8b19-12882c386af5 --vm-input 12 --presentation-filter Verse Chorus Bridge
    --ew-client-id 76955bdc-124e-4e1a-b92c-3d829ce0fb0d --vm-input 13 --presentation-filter "#sidenotes"
    --ew-client-id 5c45266b-71e3-4537-9e71-28d5acd4b2db --vm-input 14 --presentation-filter "(HCSB)" "(KJV)" "(NIV)"

If `--ew-client-id` is not specified, then EW2VM uses a hard-coded value.

Custom title/credits
--------------------

EW2VM uses a second textbox on the vMix *Title* for displaying a title or attribution/copyright notice applicable to an entire presentation/song.

The (unofficial) EasyWorship API does not appear to have a way of accessing the songwriter credits stored in the EasyWorship song database. As an alternative, EW2VM can use the text from a specially-prepared slide as the credits text to send to vMix. By default, a slide containing "Title", "Credit" or "Credits" in the slide title will have its text used by EW2VM for the purpose of credits text.

To change the word(s) EW2VM looks for in the title of the special slide, specify `--credit-slide TAG`. Multiple `TAG`s can be specified by separating with space.

Examples:

    --credit-slide credits4stream
    --credit-slide Attribution Copyright Credits

If a presentation/song contains no special credits slide, then EW2VM will use the title of the presentation/song for the purpose of credits text to send to vMix. To enforce the use of special credits slide, set `--presentation-filter` the same as `--credit-slide`.

Information
-----------

### Support

No support is provided with EW2VM. For community discussion, try the _3rd Party Software and Development_ section of the [official vMix Forums](https://forums.vmix.com/).

### Copyright and license

EW2VM Copyright (c) 2021 Michael Norton. MIT License; see <LICENSE.md> file for details.

### Trademarks

EasyWorship is a registered trademark of Softouch Development, Inc.
vMix is a registered trademark of StudioCoast Pty Ltd.

### Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

