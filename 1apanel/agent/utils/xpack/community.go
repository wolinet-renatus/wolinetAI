//go:build !xpack && !enterprise

package xpack

import "wolinet.ai/1apanel/agent/utils/xpack/helper"

var AlertProvider = helper.NewIAlertProvider()

var MultiNodeProvider = helper.NewIMultiNodeProvider()
