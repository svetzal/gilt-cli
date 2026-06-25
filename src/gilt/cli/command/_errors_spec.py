from gilt.cli.command._errors import CommandAbort


class DescribeCommandAbort:
    def it_should_store_the_given_exit_code(self):
        assert CommandAbort(2).code == 2

    def it_should_default_to_exit_code_1(self):
        assert CommandAbort().code == 1

    def it_should_be_an_exception(self):
        assert isinstance(CommandAbort(), Exception)
