import camelcaseKeys from 'camelcase-keys';

/**
 * Chuyển đổi khóa snake_case sang camelCase
 * @param data Dữ liệu phản hồi API (snake_case)
 * @returns Đối tượng đã chuyển đổi sang camelCase
 */
export function toCamelCase<T>(data: unknown): T {
    if (data === null || data === undefined) {
        return data as T;
    }
    return camelcaseKeys(data as Record<string, unknown>, { deep: true }) as T;
}
