import json
import re

from argparse import ArgumentParser, RawTextHelpFormatter

parser = ArgumentParser(formatter_class=RawTextHelpFormatter)

parser.add_argument('-r', '--report-file',
                    help='Specify the path of a JSON report file that resulted from a CIV test run.',
                    required=True)
parser.add_argument('-o', '--output-file',
                    help='Specify the file path of the analysis file to be stored as plain text with the chosen format.',
                    required=False)
parser.add_argument('-f', '--format',
                    help='(Optional) Specify in which format the analysis should be printed to stdout.\n'
                         'Supported values are:\n'
                         '\t- cli: Outputs a cli-alike analysis\n'
                         '\t- table: Outputs the analysis with rows in tabulated format\n'
                         '\t- jira: Outputs the analysis formatted with Jira markup syntax\n',
                    default='cli',
                    required=False)

spaced_indentation = ' ' * 8


def get_failed_tests_analysis(data):
    test_results = data['tests']

    analysis = {}
    for test in test_results:
        if test['outcome'] == 'failed':
            test_name = test['keywords'][0].split('[')[0]
            error_message = test['call']['crash']['message'].split('\n')[0]

            if test_name in analysis:
                if error_message in analysis[test_name]:
                    analysis[test_name][error_message] += 1
                else:
                    analysis[test_name][error_message] = 1
            else:
                analysis[test_name] = {error_message: 1}

    return analysis


def get_formatted_analysis(analysis, format):
    if format == 'table':
        formatted_analysis = get_analysis_as_spreadsheet_table(analysis)
    elif format == 'jira':
        formatted_analysis = get_analysis_as_jira_markup(analysis)
    else:
        formatted_analysis = get_analysis_as_cli(analysis)

    return '\n'.join(formatted_analysis)


def get_formatted_summary(data):
    summary_data = data['summary']

    passed_total = summary_data['passed']
    failed_total = summary_data['failed'] if 'failed' in summary_data else 0
    failed_and_passed_total = passed_total + failed_total

    success_ratio = round((passed_total * 100 / failed_and_passed_total), 2)

    summary_lines = [
        '-' * 100,
        f'Total passed:\t{passed_total}',
        f'Total failed:\t{failed_total}',
        f'Success ratio:\t{success_ratio}%',
        '-' * 100
    ]

    return '\n'.join(summary_lines)


def get_analysis_as_cli(analysis):
    rows = []

    for test_case, error_data in analysis.items():
        for err_msg, count in error_data.items():
            rows.append(f'{test_case} - {count} time(s):')
            rows.append('\t' + __parse_error_message(err_msg).replace('\n', f'\n{spaced_indentation}'))

        rows.append('-' * 100)

    return rows


def __parse_error_message(error_message):
    regex_error_generic = re.compile(r'(?:(?:AssertionError|Failed): (.*))')
    regex_error_command = re.compile(
        r"Unexpected exit code \d+ for CommandResult\(command=b?(?P<command>['|\"]?.*['|\"]?), "
        r"exit_status=(?P<exit_status>\d+), stdout=b?(?P<stdout>['|\"]?.*['|\"]?), "
        r"stderr=b?(?P<stderr>['|\"]?.*['|\"]?)\)"
    )

    extracted_message = error_message

    result = re.findall(regex_error_generic, error_message)
    if result:
        extracted_message = result[0]

        result = re.match(regex_error_command, extracted_message)
        if result:
            error_details = result.groupdict()
            composed_error_message = [
                '{0}: {1}'.format(k, v.replace(r'\n\n', f'\n{spaced_indentation}'))
                for k, v in error_details.items()
            ]
            extracted_message = '\n'.join(composed_error_message)

    return extracted_message.replace(r'\n', f'\n{spaced_indentation}')


def get_analysis_as_jira_markup(analysis):
    rows = []

    for test_case, error_data in analysis.items():
        for err_msg, count in error_data.items():
            rows.append(
                f'h4. {test_case} - {count} failure(s): ' + '{code:java}' + __parse_error_message(err_msg) + '{code}'
            )

    return rows


def get_analysis_as_spreadsheet_table(analysis):
    default_test_owner = 'Jenkins'
    default_status = 'Not Started'
    default_rerun_value = 'FALSE'
    default_delimiter = '\t'

    rows = [
        'TestCase',
        'Owner',
        'Status',
        'Fails again in rerun',
        'Rate Failure',
        'Comments'
    ]

    for test_case, error_data in analysis.items():
        for err_msg, count in error_data.items():
            formatted_err_msg = __parse_error_message(err_msg).replace(spaced_indentation, '')
            formatted_err_msg = formatted_err_msg.replace('\n', ' | ')

            row_details = [
                test_case,
                default_test_owner,
                default_status,
                str(count),
                default_rerun_value,
                formatted_err_msg
            ]

            rows.append(default_delimiter.join(row_details))

    return rows


if __name__ == '__main__':
    args = parser.parse_args()

    with open(args.report_file) as f:
        report_data = json.load(f)

    formatted_summary = get_formatted_summary(report_data)
    print(formatted_summary)

    if 'failed' not in report_data['summary']:
        print('Congratulations! No test failures found.')
        exit(0)

    analysis = get_failed_tests_analysis(report_data)
    formatted_analysis = get_formatted_analysis(analysis, format=args.format)

    print(formatted_analysis)

    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(f'{formatted_summary}\n{formatted_analysis}')
