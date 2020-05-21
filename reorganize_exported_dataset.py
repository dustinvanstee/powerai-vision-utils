#!/usr/bin/env python
import paiv_utils as paiv
import argparse as ap

class SmartFormatterMixin(ap.HelpFormatter):
    # ref:
    # http://stackoverflow.com/questions/3853722/python-argparse-how-to-insert-newline-in-the-help-text
    # @IgnorePep8

    def _split_lines(self, text, width):
        # this is the RawTextHelpFormatter._split_lines
        if text.startswith('S|'):
            return text[2:].splitlines()
        return ap.HelpFormatter._split_lines(self, text, width)


class CustomFormatter(ap.RawDescriptionHelpFormatter, SmartFormatterMixin):
    '''Convenience formatter_class for argparse help print out.'''


def _parser():
    parser = ap.ArgumentParser(description='Tool Reorganize an exported IBM Visual Insights Exported Directory'
                                           'Supports Classification data only and reorganizes it into folders'
                                           'with each subfolder being a label'
                                           'Example :'
                                           'python reorganize_exported_dataset.py --directory_in /tmp/exported_directory --directory_out /tmp/directory_out',
                               formatter_class=CustomFormatter)

    parser.add_argument(
        '--directory_in', action='store', nargs='?', required=True,
        help='S|--directory_in=<exported PAIV directory_path>'
             'Default: %(default)s')

    parser.add_argument(
        '--directory_out', action='store', nargs='?', required=True,
        help='S|--directory_out=<path where you want to resave data>'
             'Default: %(default)s')

    args = parser.parse_args()

    return args


def main():
    # Parse command line argument
    args = _parser()
    #args.force_refresh = True
    for argk in vars(args) :
        print(argk,vars(args)[argk])
    paiv.reformat_paiv_cls_export(args.directory_in, args.directory_out)

if __name__== "__main__":
  main()

# Todo : add threading for quicker video building
# Todo : add custom logic for tracking ball touches with denoising / smoothing
# Todo : add custom logic for displaying number of players at any given time with denoising / smoothing