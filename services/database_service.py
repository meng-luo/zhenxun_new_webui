"""数据库服务"""
from tortoise import Tortoise

from zhenxun.configs.config import BotConfig

from ..exceptions import SystemException, ValidationException
from ..models.database import (
    SqlExecuteRequest,
    SqlExecuteResult,
    TableDataResult,
    TableRowData,
)

# SQL 类型映射
type2sql = {
    "sqlite": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    "mysql": "SHOW TABLES",
    "postgres": (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    ),
}


class DatabaseService:
    """数据库服务"""

    @staticmethod
    async def get_table_list() -> list[str]:
        """获取表列表

        返回:
            list[str]: 表名列表
        """
        try:
            db = Tortoise.get_connection("default")
            sql_type = BotConfig.get_sql_type()
            sql = type2sql.get(sql_type)
            if not sql:
                raise ValidationException(f"不支持的数据库类型：{sql_type}")

            query = await db.execute_query_dict(sql)
            return [next(iter(row.values())) for row in query]
        except Exception as e:
            raise SystemException(f"获取表列表失败：{e!s}")

    @staticmethod
    async def get_table_columns(table_name: str) -> list[dict]:
        """获取表字段

        参数:
            table_name: 表名

        返回:
            list[dict]: 字段列表，包含 name, type, nullable, default, primary_key
        """
        try:
            db = Tortoise.get_connection("default")
            sql_type = BotConfig.get_sql_type()

            columns = []
            if sql_type == "sqlite":
                sql = f"PRAGMA table_info({table_name})"
                query = await db.execute_query_dict(sql)
                for row in query:
                    columns.append(
                        {
                            "name": row.get("name", ""),
                            "type": row.get("type", ""),
                            "nullable": row.get("notnull", 0) == 0,
                            "default": row.get("dflt_value"),
                            "primary_key": row.get("pk", 0) == 1,
                        }
                    )
            elif sql_type == "mysql":
                sql = f"SHOW COLUMNS FROM {table_name}"
                query = await db.execute_query_dict(sql)
                for row in query:
                    columns.append(
                        {
                            "name": row.get("Field", ""),
                            "type": row.get("Type", ""),
                            "nullable": row.get("Null", "") == "YES",
                            "default": row.get("Default"),
                            "primary_key": row.get("Key", "") == "PRI",
                        }
                    )
            elif sql_type == "postgres":
                sql = """
                    SELECT
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        CASE
                            WHEN pk.col_name IS NOT NULL
                            THEN true ELSE false
                        END as is_primary
                    FROM information_schema.columns
                    LEFT JOIN (
                        SELECT kcu.column_name as col_name
                        FROM information_schema.table_constraints tco
                        JOIN information_schema.key_column_usage kcu
                            ON tco.constraint_name = kcu.constraint_name
                        WHERE tco.constraint_type = 'PRIMARY KEY'
                        AND tco.table_name = '{table_name}'
                    ) pk ON information_schema.columns.column_name = pk.col_name
                    WHERE information_schema.columns.table_name = '{table_name}'
                    ORDER BY ordinal_position
                """
                query = await db.execute_query_dict(sql)
                for row in query:
                    columns.append(
                        {
                            "name": row.get("column_name", ""),
                            "type": row.get("data_type", ""),
                            "nullable": row.get("is_nullable", "NO") == "YES",
                            "default": row.get("column_default"),
                            "primary_key": row.get("is_primary", False),
                        }
                    )
            else:
                raise ValidationException(f"不支持的数据库类型：{sql_type}")

            return columns
        except Exception as e:
            raise SystemException(f"获取表字段失败：{e!s}")

    @staticmethod
    async def get_table_data(
        table_name: str, page: int = 1, page_size: int = 50
    ) -> TableDataResult:
        """获取表数据

        参数:
            table_name: 表名
            page: 页码
            page_size: 每页数量

        返回:
            TableDataResult: 表数据结果
        """
        try:
            # 获取模型类
            model_cls = Tortoise.apps["models"].get(table_name)
            if not model_cls:
                # 尝试从其他 app 获取
                for app_name, app_models in Tortoise.apps.items():
                    if table_name in app_models:
                        model_cls = app_models[table_name]
                        break

            if not model_cls:
                # 如果没有对应的模型，使用通用查询
                db = Tortoise.get_connection("default")
                sql_type = BotConfig.get_sql_type()

                # 获取总数
                count_sql = f"SELECT COUNT(*) as count FROM {table_name}"
                count_result = await db.execute_query_dict(count_sql)
                total = count_result[0]["count"] if count_result else 0

                # 获取数据
                offset = (page - 1) * page_size
                if sql_type == "sqlite":
                    data_sql = (
                        f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset}"
                    )
                elif sql_type == "mysql":
                    data_sql = (
                        f"SELECT * FROM {table_name} LIMIT {offset}, {page_size}"
                    )
                elif sql_type == "postgres":
                    data_sql = (
                        f"SELECT * FROM {table_name} LIMIT {page_size} OFFSET {offset}"
                    )
                else:
                    raise ValidationException(f"不支持的数据库类型：{sql_type}")

                data = await db.execute_query_dict(data_sql)

                items = []
                for i, row in enumerate(data):
                    items.append(
                        TableRowData(
                            id=row.get("id", i),
                            data=row,
                        )
                    )

                return TableDataResult(
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    has_next=offset + len(data) < total,
                    has_prev=page > 1,
                )

            # 使用模型查询
            total = await model_cls.all().count()
            offset = (page - 1) * page_size
            data = await model_cls.all().limit(page_size).offset(offset)

            items = []
            for i, row in enumerate(data):
                row_data = row.to_dict() if hasattr(row, "to_dict") else row.__dict__
                items.append(
                    TableRowData(
                        id=getattr(row, "id", i),
                        data=row_data,
                    )
                )

            return TableDataResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                has_next=offset + len(items) < total,
                has_prev=page > 1,
            )
        except Exception as e:
            raise SystemException(f"获取表数据失败：{e!s}")

    @staticmethod
    async def execute_sql(request: SqlExecuteRequest) -> SqlExecuteResult:
        """执行 SQL

        参数:
            request: SQL 请求

        返回:
            SqlExecuteResult: 执行结果
        """
        db = Tortoise.get_connection("default")
        sql = request.sql.strip()

        # 判断是否为查询语句
        sql_lower = sql.lower()
        is_query = sql_lower.startswith(
            ("select", "show", "describe", "explain", "pragma")
        )

        if is_query:
            # 查询语句返回结果数据
            result = await db.execute_query_dict(sql)
            return SqlExecuteResult(
                success=True,
                message="执行成功",
                data=result,
                rows_affected=len(result),
            )
        else:
            # 非查询语句（INSERT、UPDATE、DELETE、CREATE、DROP 等）返回影响行数
            rows_affected = await db.execute_query(sql)
            return SqlExecuteResult(
                success=True,
                message="执行成功",
                data=None,
                rows_affected=rows_affected[0] if rows_affected else 0,
            )

    @staticmethod
    async def get_table_row_count(table_name: str) -> int:
        """获取表行数

        参数:
            table_name: 表名

        返回:
            int: 行数
        """
        try:
            model_cls = Tortoise.apps["models"].get(table_name)
            if model_cls:
                return await model_cls.all().count()

            db = Tortoise.get_connection("default")
            sql_type = BotConfig.get_sql_type()
            if sql_type == "sqlite":
                sql = f"SELECT COUNT(*) as count FROM {table_name}"
            elif sql_type == "mysql":
                sql = f"SELECT COUNT(*) as count FROM {table_name}"
            elif sql_type == "postgres":
                sql = f"SELECT COUNT(*) as count FROM {table_name}"
            else:
                return 0

            result = await db.execute_query_dict(sql)
            return result[0]["count"] if result else 0
        except Exception:
            return 0
