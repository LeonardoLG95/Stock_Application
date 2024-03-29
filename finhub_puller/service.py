from migration_handler import migration
from puller import Puller
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

import asyncio
from drivers.timescale.api_driver import TimescaleDriver

from endpoints import END_POINT
from utils.logger import Logger

from env import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


# Start migration
# migration()

APP = FastAPI()

# To allow React app connect to this app
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGGER = Logger("API")
DB = TimescaleDriver(
    log=LOGGER,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    db=DB_NAME,
)


APP.state.pull_task = None


@APP.get(END_POINT["start"])
async def start_puller():
    async def pull():
        LOGGER.info("Starting puller!")
        puller = Puller()
        await puller.start()
        await puller.pull_tasks()
        await puller.close()

    if APP.state.pull_task and APP.state.pull_task.done() is False:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"response": "Puller is already working"},
        )

    APP.state.pull_task = asyncio.create_task(pull())

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": "Puller started"},
    )


@APP.get(END_POINT["is_running"])
async def is_running():
    if APP.state.pull_task is None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"response": False},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": not APP.state.pull_task.done()},
    )


@APP.get(END_POINT["symbols"])
async def get_symbols() -> JSONResponse:
    stocks_list = await DB.select_stocks()
    if stocks_list is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info("List of symbols retrieved")

    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"response": stocks_list}
    )


@APP.post(END_POINT["history"])
async def get_symbol_data(request: Request) -> JSONResponse:
    request = await request.json()
    symbol = request.get("symbol")
    resolution = request.get("resolution")

    prices = await DB.select_history(symbol, resolution)
    if prices is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info(f"Prices for symbol {symbol} on resolution {resolution} retrieved")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": prices if len(prices) > 0 else None},
    )


@APP.post(END_POINT["symbol_prices"])
async def get_symbol_data(request: Request) -> JSONResponse:
    request = await request.json()

    symbol = request.get("symbol")

    start_operation = request.get("start_operation")
    start_operation = datetime.strptime(start_operation, "%Y-%m-%dT%H:%M:%S.%fZ")

    end_operation = request.get("end_operation")
    if end_operation is not None:
        end_operation = datetime.strptime(end_operation, "%Y-%m-%dT%H:%M:%S.%fZ")

    resolution = request.get("resolution")

    prices = await DB.select_symbol_prices(
        symbol, start_operation, end_operation, resolution
    )
    if prices is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info(f"Prices for symbol {symbol} on resolution {resolution} retrieved")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": prices if len(prices) > 0 else None},
    )


@APP.get(END_POINT["by_macd"])
async def get_symbol_data() -> JSONResponse:
    stocks = await DB.select_recommendations_by_macd()
    if stocks is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info(f"Recommended stocks by MACD pulled")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": stocks if len(stocks) > 0 else None},
    )


@APP.post(END_POINT["industry"])
async def get_symbol_industry(request: Request) -> JSONResponse:
    request = await request.json()

    symbol = request.get("symbol")

    industry = await DB.select_symbol_industry(symbol)
    if industry is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info(f"Stock industry pulled")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": industry},
    )


@APP.post(END_POINT["last_price"])
async def get_symbol_last_price(request: Request) -> JSONResponse:
    request = await request.json()

    symbol = request.get("symbol")

    price = await DB.select_symbol_last_price(symbol)
    if price is None:
        raise HTTPException(status_code=404, detail={"response": "Query not found"})

    LOGGER.info(f"Last stock close price pulled")

    if not isinstance(price, float):
        price = None

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"response": price},
    )
