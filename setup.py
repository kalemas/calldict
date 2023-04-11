from distutils.core import setup

setup(
    name='calldict',
    packages=['calldict'],
    version='0.4',
    description='Protocol to markup and evaluate functions in data structures',
    author='Konstantin Maslyuk',
    author_email='kostyamaslyuk@gmail.com',
    url='https://github.com/kalemas/calldict',
    download_url='https://github.com/kalemas/calldict/archive/master.zip',
    keywords=['dict', 'evaluation', 'yaml'],
    classifiers=[],
    extras_require={
        'dev': ['yapf'],
        'test': ['pytest'],
    },
)
