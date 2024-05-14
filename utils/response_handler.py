from enum import Enum


class ResponseTypes(Enum):
    QUERY = "Q"
    MEMORY = "M"
    FEEDBACK = "F"
    INVALID = "I"


class ResponseHandler:
    def __init__(self, type_: ResponseTypes):
        self.type_ = type_

    def handle_response(self, response: str):
        pass


class QueryResponseHandler(ResponseHandler):
    def __init__(self):
        super().__init__(ResponseTypes.QUERY)

    def get_context(self, *args) -> str:
        return f"Context: database response was {args[0]['result']}"


class MemoryResponseHandler(ResponseHandler):
    def __init__(self):
        super().__init__(ResponseTypes.MEMORY)

    def get_context(self, *args) -> str:
        return f"Context: respond using memory history."
    

class FeedbackResponseHandler(ResponseHandler):

    def __init__(self):
        super().__init__(ResponseTypes.FEEDBACK)

    def get_context(self, *args) -> str:
        return "Context: user provided feedback."
    

class InvalidResponseHandler(ResponseHandler):

    def __init__(self):
        super().__init__(ResponseTypes.INVALID)

    def get_context(self, *args) -> str:
        return f"Context: user provided invalid query."


class ResponseHandlerFactory:
    @staticmethod
    def create_response_handler(type_: ResponseTypes):
        if type_ == ResponseTypes.QUERY:
            return QueryResponseHandler()
        elif type_ == ResponseTypes.MEMORY:
            return MemoryResponseHandler()
        elif type_ == ResponseTypes.FEEDBACK:
            return FeedbackResponseHandler()
        elif type_ == ResponseTypes.INVALID:
            return InvalidResponseHandler()
        else:
            return InvalidResponseHandler()
