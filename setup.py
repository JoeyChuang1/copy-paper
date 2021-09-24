import os
import setuptools
import sys


# Load README to get long description.
with open('README.md') as f:
    _LONG_DESCRIPTION = f.read()


setuptools.setup(
    name='nullprompt',
    version='0.0.1',
    description=(
        'Code for "Cutting Down on Prompts and Parameters: '
        'Simple Few-Shot Learning with Language Models".'
    ),
    long_description=_LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author='UCI NLP',
    url='https://github.com/ucinlp/null-prompts',
    packages=setuptools.find_packages(),
    install_requires=[
        'adapter-transformers==1.1.0',
        'Jinja2==2.7.0',
        'PyYAML==5.3.1',
        'tensorboard==2.4.1',
        'scipy==1.3.1',
    ],
    extras_require={
        'test': ['pytest']
    },
    classifiers=[
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
    keywords='text nlp machinelearning',
)
