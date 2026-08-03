from ione_hrp.common.fixture_policy import get_frappe_fixture_hooks

app_name = "ione_hrp"
app_title = "美妍伊人医院 HRP"
app_publisher = "美妍伊人医疗科技有限公司"
app_description = "基于 Frappe 生态的医院资源规划平台"
app_email = "317395616@qq.com"
app_license = "License Review Required"
source_link = "https://github.com/jerry317395616/ione_hrp"

required_apps = ["frappe/erpnext", "frappe/hrms"]

app_logo_url = "/assets/ione_hrp/images/ione-hrp-logo.svg"
app_home = "/desk/hrp"
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": app_home,
		"has_permission": "ione_hrp.permissions.check_app_permission",
		"sequence_id": 3,
	}
]

after_install = "ione_hrp.setup.install.after_install"
after_migrate = "ione_hrp.setup.install.after_migrate"
before_uninstall = "ione_hrp.setup.install.before_uninstall"

before_request = ["ione_hrp.services.audit_context.start_http_audit_context"]
after_request = ["ione_hrp.services.audit_context.finish_http_audit_context"]
before_job = ["ione_hrp.services.audit_context.start_job_audit_context"]
after_job = ["ione_hrp.services.audit_context.finish_job_audit_context"]

# Add standard DocType extensions here. Prefer extend_doctype_class over overrides.
extend_doctype_class = {}
doc_events = {}

permission_query_conditions = {
	"HRP External Code Mapping": "ione_hrp.hrp_master_data.permissions.external_code_mapping_query",
	"HRP Master Data Request": "ione_hrp.hrp_master_data.permissions.master_data_request_query",
}
has_permission = {
	"HRP External Code Mapping": "ione_hrp.hrp_master_data.permissions.can_read_external_code_mapping",
	"HRP Master Data Request": "ione_hrp.hrp_master_data.permissions.can_read_master_data_request",
}

scheduler_events = {
	"daily": [
		"ione_hrp.setup.maintenance.daily_maintenance",
	],
}

fixture_auto_order = True
fixtures = get_frappe_fixture_hooks()

export_python_type_annotations = True
require_type_annotated_api_methods = True
