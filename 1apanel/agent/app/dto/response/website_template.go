package response

import (
	"wolinet.ai/1apanel/agent/app/model"
)

type WebsiteTemplateDTO struct {
	model.WebsiteTemplate
}

type WebsiteTemplateOutputDTO struct {
	model.WebsiteTemplateOutput
	TemplateName string `json:"templateName"`
}

type WebsitePreviewDTO struct {
	HTML string `json:"html"`
}
