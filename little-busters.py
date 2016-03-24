from shutil import copyfile
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZipFile
import os.path
import click
from PIL import Image


def calculate_average_resolution(sizes):
    """Returns the average dimensions for a list of resolution tuples."""
    count = len(sizes)
    horizontal = sum([x[0] for x in sizes]) / count
    vertical = sum([x[1] for x in sizes]) / count
    return (horizontal, vertical)


def create_archive(archive, excluded):
    """Creates a new zip archive file by excluding files at positions found in
    excluded.
    """
    new_archive_file = NamedTemporaryFile()
    temporary_directory = TemporaryDirectory()
    new_archive = ZipFile(new_archive_file, 'w')
    for index, filename in enumerate(archive.namelist()):
        if index not in excluded:
            archive.extract(filename, path=temporary_directory.name)
            new_archive.write(os.path.join(temporary_directory.name, filename))
    temporary_directory.cleanup()
    return new_archive_file


def detect_double_spreads(sizes, treshold):
    """Double spreads are single image files that combine two pages into one
    image to simulate the two-page spread of a magazine. Double spreads are
    detected by identifying images that are twice as wide as the average but
    have a height consistent with the rest of the pages.

    This function will overwrite any double spread sizes with (x/2, y) in order
    to more accurately give an average resolution for one single page and not
    to remove any double spread pages.
    """
    average = calculate_average_resolution(sizes)
    for index, size in enumerate(sizes):
        horizontal_diff = abs(1 - size[0] / 2 / average[0])
        vertical_diff = abs(1 - size[1] / average[1])
        if horizontal_diff < treshold and vertical_diff < treshold:
            sizes[index] = (size[0] / 2, size[1])


def detect_non_pages(sizes, treshold):
    """Returns a list of indexes for files that do not fit within resolution
    threshold.
    """
    average = calculate_average_resolution(sizes)
    average_resolution = average[0] * average[1]
    indexes = []
    for index, size in enumerate(sizes):
        resolution = size[0] * size[1]
        size_diff = resolution / average_resolution
        if 1 - size_diff > treshold:
            indexes.append((index, size_diff))
    return indexes


def get_sizes(archive):
    """Returns a list of sizes for files inside a ZipFile object."""
    sizes = []
    for filename in archive.namelist():
        with archive.open(filename) as file:
            image = Image.open(file)
            sizes.append(image.size)
    return sizes


@click.command()
@click.option('--dry-run', is_flag=True,
              help='Do not overwrite any files.')
@click.option('--threshold', default=0.2,
              help='Percent value images may differ from average resolution')
@click.argument('files', nargs=-1)
def main(dry_run, threshold, files):
    """Goes through one or more zip archives in order to find images with
    resolution differing too much from the average.
    """
    target_diff = 1 - threshold
    for file in files:
        archive = ZipFile(file)
        sizes = get_sizes(archive)
        detect_double_spreads(sizes, threshold)
        non_pages = detect_non_pages(sizes, threshold)
        if non_pages:
            filename = click.style(os.path.basename(file), bold=True)
            file_count = len(archive.namelist())
            for index, diff in non_pages:
                click.echo('{}: p{:0>3}/{:0>3} ({:.1%} < {:.0%})'
                           .format(filename, index + 1,
                                   file_count, diff, target_diff))
            if not dry_run:
                new_file = create_archive(archive, [x[0] for x in non_pages])
                copyfile(new_file.name, file)

if __name__ == '__main__':
    main()
